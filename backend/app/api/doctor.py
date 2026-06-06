from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, require_roles
from app.core.timezone import BEIJING_TZ, now_beijing
from app.models.user import User
from app.models.doctor import Doctor
from app.models.consent import Consent
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.doctor import AccessRequestCreate
from app.services.masking import mask_record_by_scope
from app.services.audit_service import request_audit_context, write_audit_log
from app.services.crypto_service import MedicalRecordCryptoError, encrypt_record_json

router = APIRouter(prefix="/api/doctor", tags=["医生业务模块"])


class MedicalRecordUpdateRequest(BaseModel):
    record: dict[str, Any]


def ensure_doctor_approved(db: Session, user: User) -> None:
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if doctor is None or not doctor.verified:
        raise HTTPException(
            status_code=403,
            detail="Doctor account is pending admin approval",
        )


def consent_display_status(consent: Consent) -> str:
    end_time = consent.end_time
    if end_time is not None and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=BEIJING_TZ)
    elif end_time is not None:
        end_time = end_time.astimezone(BEIJING_TZ)

    if (
        consent.status == "ACTIVE"
        and end_time is not None
        and end_time <= now_beijing()
    ):
        return "EXPIRED"
    return consent.status


def mask_address(address: str | None) -> str:
    if not address:
        return ""
    return str(address).split(",")[0].strip()


def consent_priority(consent: Consent) -> tuple[int, int]:
    status_rank = {
        "ACTIVE": 4,
        "PENDING": 3,
        "REJECTED": 2,
        "REVOKED": 1,
    }.get(consent_display_status(consent), 0)
    scope_rank = {"EXTRA": 2, "DEFAULT": 1}.get(consent.record_scope, 0)
    return status_rank, scope_rank


def get_valid_consent(
    db: Session,
    *,
    patient_id: int,
    doctor_user_id: int,
    required_scope: str | None = None,
) -> Consent | None:
    query = db.query(Consent).filter(
        Consent.patient_id == patient_id,
        Consent.doctor_id == doctor_user_id,
        Consent.status == "ACTIVE",
        Consent.end_time.isnot(None),
        Consent.end_time > now_beijing(),
    )

    if required_scope is not None:
        query = query.filter(Consent.record_scope == required_scope)

    return query.order_by(Consent.record_scope.desc(), Consent.end_time.desc()).first()


def has_active_full_consent(db: Session, *, patient_id: int, doctor_user_id: int) -> bool:
    return get_valid_consent(
        db,
        patient_id=patient_id,
        doctor_user_id=doctor_user_id,
        required_scope="EXTRA",
    ) is not None


@router.get("/me")
def get_doctor_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR")),
):
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "name": doctor.name,
        "department": doctor.department,
        "license_no": doctor.license_no,
        "verified": doctor.verified,
    }

# 获取名下授权患者列表
@router.get("/my-patients")
def get_my_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    # Query all consent records for this doctor (including PENDING, ACTIVE, REVOKED)
    consents = db.query(Consent).filter(
        Consent.doctor_id == current_user.id
    ).all()

    best_consents_by_patient: dict[int, Consent] = {}
    for consent in consents:
        current_best = best_consents_by_patient.get(consent.patient_id)
        if current_best is None or consent_priority(consent) > consent_priority(current_best):
            best_consents_by_patient[consent.patient_id] = consent
    
    result = []
    for consent in best_consents_by_patient.values():
        # Get patient info
        patient = db.query(Patient).filter(Patient.id == consent.patient_id).first()
        if patient:
            result.append({
                "id": patient.id,
                "full_name": patient.full_name,
                "gender": patient.gender,
                "birth_date": patient.birth_date,
                "consent_status": consent_display_status(consent),      # ACTIVE, PENDING, REVOKED, EXPIRED
                "scope": consent.record_scope,         # DEFAULT, EXTRA
                "consent_id": consent.id
            })
    
    return {"patient_list": result}

# 提交额外病历访问申请
@router.post("/access-requests")
def submit_access_request(
    info: AccessRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    patient = db.query(Patient).filter(Patient.id == info.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    if info.record_scope == "DEFAULT" and has_active_full_consent(
        db,
        patient_id=info.patient_id,
        doctor_user_id=current_user.id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Already has active full access; default access is covered",
        )

    existing_pending = db.query(Consent).filter(
        Consent.patient_id == info.patient_id,
        Consent.doctor_id == current_user.id,
        Consent.status == "PENDING",
    ).first()
    if existing_pending:
        raise HTTPException(status_code=400, detail="Already has a pending request")

    existing_same_scope = db.query(Consent).filter(
        Consent.patient_id == info.patient_id,
        Consent.doctor_id == current_user.id,
        Consent.record_scope == info.record_scope,
    ).first()
    
    if existing_same_scope:
        existing_status = consent_display_status(existing_same_scope)
        if existing_status == "ACTIVE":
            raise HTTPException(status_code=400, detail="Already has active access for this scope")
        elif existing_status in {"REJECTED", "REVOKED", "EXPIRED"}:
            existing_same_scope.status = "PENDING"
            existing_same_scope.request_reason = info.reason
            existing_same_scope.consent_source = "EXPLICIT_REQUEST"
            existing_same_scope.start_time = None
            existing_same_scope.end_time = None
            existing_same_scope.approved_at = None
            existing_same_scope.revoked_at = None
            consent_for_log = existing_same_scope
        else:
            raise HTTPException(status_code=400, detail="Invalid status")
    else:
        consent_for_log = Consent(
            patient_id=info.patient_id,
            doctor_id=current_user.id,
            record_scope=info.record_scope,
            status="PENDING",
            request_reason=info.reason,
            consent_source="EXPLICIT_REQUEST"
        )
        db.add(consent_for_log)
        db.flush()
    
    write_audit_log(
        db,
        action="CONSENT_REQUEST",
        actor=current_user,
        target_type="patient",
        target_id=info.patient_id,
        doctor_id=current_user.id,
        patient_id=info.patient_id,
        consent_id=consent_for_log.id,
        record_scope=info.record_scope,
        outcome="SUCCESS",
        detail=info.reason,
        **request_audit_context(request),
    )
    db.commit()
    return {"msg": "Access request submitted, waiting for patient approval"}
# 查看脱敏后患者病历
# 场景1/3/5：查看脱敏病历 + 权限校验 + 日志记录
@router.get("/patients/{patient_id}/records")
def get_patient_mask_record(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    from datetime import datetime, timedelta
    ensure_doctor_approved(db, current_user)
    from app.models.medical_record import MedicalRecord
    from app.services.crypto_service import decrypt_record_json
    from app.models.access_log import AccessLog
    from app.models.patient import Patient
    
    # 1. 检查有效授权
    valid_consent = get_valid_consent(
        db,
        patient_id=patient_id,
        doctor_user_id=current_user.id,
    )

    # 2. 记录审计日志
    log = AccessLog(
        doctor_id=current_user.id,
        patient_id=patient_id,
        consent_id=valid_consent.id if valid_consent else None,
        action="ACCESS" if valid_consent else "DENIED",
        record_scope=valid_consent.record_scope if valid_consent else None
    )
    db.add(log)
    write_audit_log(
        db,
        action="VIEW_RECORD",
        actor=current_user,
        target_type="patient",
        target_id=patient_id,
        doctor_id=current_user.id,
        patient_id=patient_id,
        consent_id=valid_consent.id if valid_consent else None,
        record_scope=valid_consent.record_scope if valid_consent else None,
        outcome="SUCCESS" if valid_consent else "DENIED",
        detail="Doctor viewed patient medical record" if valid_consent else "Doctor record view denied",
        **request_audit_context(request),
    )
    db.commit()

    # 3. 无权限拒绝
    if not valid_consent:
        raise HTTPException(status_code=403, detail="No access permission or authorization expired")

    # 4. 获取患者基本信息
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # 5. 查询并解密所有病历（不只是最新的一条）
    medical_records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient_id
    ).order_by(MedicalRecord.created_at.desc()).all()
    
    # 合并所有病历数据
    all_conditions = []
    all_medications = []
    all_observations = []
    all_procedures = []
    all_encounters = []
    latest_updated_at = None
    latest_updated_by = None
    latest_record_id = None
    
    for record in medical_records:
        try:
            clinical_data = decrypt_record_json(record.encrypted_data, record.nonce)
            all_conditions.extend(clinical_data.get("conditions", []))
            all_medications.extend(clinical_data.get("medications", []))
            all_observations.extend(clinical_data.get("observations", []))
            all_procedures.extend(clinical_data.get("procedures", []))
            all_encounters.extend(clinical_data.get("encounters", []))
            
            # 记录最新更新的信息
            if record.updated_at and (latest_updated_at is None or record.updated_at > latest_updated_at):
                latest_updated_at = record.updated_at
                latest_updated_by = record.updated_by_doctor_id
                latest_record_id = record.id
        except Exception as e:
            print(f"Decryption failed for record {record.id}: {e}")
            continue
    
    # 去重函数（根据 id 字段）
    def dedupe_by_id(items, key="id"):
        seen = set()
        unique = []
        for item in items:
            item_id = item.get(key)
            if item_id and item_id not in seen:
                seen.add(item_id)
                unique.append(item)
            elif not item_id:
                unique.append(item)
        return unique
    
    # 去重
    all_conditions = dedupe_by_id(all_conditions)
    all_medications = dedupe_by_id(all_medications)
    all_observations = dedupe_by_id(all_observations)
    all_procedures = dedupe_by_id(all_procedures)
    all_encounters = dedupe_by_id(all_encounters, key="id")
    
    # 6. 手机号脱敏函数
    def mask_phone(phone):
        if not phone:
            return ""
        phone_str = str(phone)
        if len(phone_str) >= 7:
            return phone_str[:3] + "****" + phone_str[-4:]
        return phone_str
    
    # 7. 日期过滤函数
    def filter_records_by_date(records, days=365):
        """过滤一年内的记录"""
        if not records:
            return []
        one_year_ago = now_beijing() - timedelta(days=days)
        filtered = []
        for record in records:
            date_str = record.get("recorded_date") or record.get("effective_datetime") or record.get("authored_on") or record.get("performed_datetime")
            if date_str:
                try:
                    if isinstance(date_str, str):
                        record_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        record_date = date_str
                    if record_date >= one_year_ago:
                        filtered.append(record)
                except:
                    filtered.append(record)
            else:
                filtered.append(record)
        return filtered
    
    # 8. 构建诊断列表
    def build_diagnosis_list(conds):
        return [{
            "name": cond.get("code", ""),
            "department": cond.get("department","Not Classified"),
            "status": cond.get("clinical_status", "active"),
            "date": cond.get("recorded_date", "")[:10] if cond.get("recorded_date") else "",
            "encounter_id": cond.get("encounter_id")
        } for cond in conds]
    
    # 9. 构建用药列表
    def build_medications_list(meds):
        return [{
            "name": med.get("medication", ""),
            "start_date": med.get("authored_on", "")[:10] if med.get("authored_on") else "",
            "stop_date": med.get("stop_date", "")[:10] if med.get("stop_date") else ""
        } for med in meds if med.get("medication")]
    
    # 10. 构建检查结果列表
    def build_observations_list(obs):
        return [{
            "test_name": obs.get("code", ""),
            "value": obs.get("value", ""),
            "date": obs.get("effective_datetime", "")[:10] if obs.get("effective_datetime") else ""
        } for obs in obs if obs.get("code")]
    
    # 11. 构建手术列表
    def build_procedures_list(procs):
        return [{
            "name": proc.get("code", ""),
            "date": proc.get("performed_datetime", "")[:10] if proc.get("performed_datetime") else ""
        } for proc in procs if proc.get("code")]
    
    # 12. 按授权范围返回
    scope = valid_consent.record_scope
    
    if scope == "DEFAULT":
        # 默认范围：只显示一年内的记录
        filtered_conditions = filter_records_by_date(all_conditions, 365)
        
        result = {
            "record_id": latest_record_id,
            "name": patient.full_name,
            "gender": patient.gender,
            "phone": mask_phone(patient.phone),
            "address": mask_address(patient.address),
            "birth_date": str(patient.birth_date) if patient.birth_date else "",
            "visits": len(all_encounters),
            "diagnoses": len(filtered_conditions),
            "lab_results": "Limited - apply full access to view",
            "medications": "Limited - apply full access to view",
            "procedures": "Limited - apply full access to view",
            "diagnosis_list": build_diagnosis_list(filtered_conditions),
            "updated_at": latest_updated_at,
            "updated_by_doctor_id": latest_updated_by,
            "record_scope": scope,
            "message": f"Default scope - only records from the last year ({len(filtered_conditions)} diagnoses found)"
        }
        if len(filtered_conditions) == 0:
            result["message"] = "Default scope - no medical records in the last year"
    else:
        # 额外授权范围：完整信息（显示所有记录）
        result = {
            "record_id": latest_record_id,
            "name": patient.full_name,
            "gender": patient.gender,
            "phone": patient.phone,
            "address": patient.address,
            "birth_date": str(patient.birth_date) if patient.birth_date else "",
            "visits": len(all_encounters),
            "diagnoses": len(all_conditions),
            "lab_results": build_observations_list(all_observations),
            "medications": build_medications_list(all_medications),
            "procedures": build_procedures_list(all_procedures),
            "diagnosis_list": build_diagnosis_list(all_conditions),
            "raw_record": {
                "conditions": all_conditions,
                "medications": all_medications,
                "observations": all_observations,
                "procedures": all_procedures,
                "encounters": all_encounters
            },
            "updated_at": latest_updated_at,
            "updated_by_doctor_id": latest_updated_by,
            "record_scope": scope,
            "message": "Full access - all medical records are shown"
        }
    
    return {"medical_record": result}

@router.put("/patients/{patient_id}/records/{record_id}")
def update_patient_record(
    patient_id: int,
    record_id: int,
    payload: MedicalRecordUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR")),
):
    ensure_doctor_approved(db, current_user)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    record = db.query(MedicalRecord).filter(
        MedicalRecord.id == record_id,
        MedicalRecord.patient_id == patient_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Medical record not found")

    valid_consent = get_valid_consent(
        db,
        patient_id=patient_id,
        doctor_user_id=current_user.id,
        required_scope="EXTRA",
    )
    if valid_consent is None:
        write_audit_log(
            db,
            action="DOCTOR_RECORD_EDIT_DENIED",
            actor=current_user,
            target_type="medical_record",
            target_id=record_id,
            doctor_id=current_user.id,
            patient_id=patient_id,
            outcome="DENIED",
            detail="Doctor record overwrite denied: no active EXTRA consent",
            **request_audit_context(request),
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Full access permission is required to edit this medical record",
        )

    write_audit_log(
        db,
        action="DOCTOR_RECORD_EDIT_AUTHORIZED",
        actor=current_user,
        target_type="medical_record",
        target_id=record.id,
        doctor_id=current_user.id,
        patient_id=patient_id,
        consent_id=valid_consent.id,
        record_scope=valid_consent.record_scope,
        outcome="SUCCESS",
        detail="Doctor permission checked before record overwrite",
        **request_audit_context(request),
    )

    try:
        encrypted_data, nonce = encrypt_record_json(payload.record)
    except MedicalRecordCryptoError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to encrypt medical record") from exc

    record.encrypted_data = encrypted_data
    record.nonce = nonce
    record.updated_at = now_beijing()
    record.updated_by_doctor_id = current_user.id
    db.commit()

    return {
        "record_id": record.id,
        "patient_id": patient_id,
        "updated_at": record.updated_at,
        "updated_by_doctor_id": record.updated_by_doctor_id,
    }


@router.get("/search-patients")
def search_patients(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    patients = db.query(Patient).filter(
        Patient.full_name.ilike(f"%{q}%")
    ).limit(20).all()
    
    # 获取医生所有的授权记录
    existing_consents = db.query(Consent).filter(
        Consent.doctor_id == current_user.id
    ).all()
    
    # 创建 patient_id -> 授权信息的映射
    consent_map = {}
    for c in existing_consents:
        current = consent_map.get(c.patient_id)
        if current and current["priority"] >= consent_priority(c):
            continue
        consent_map[c.patient_id] = {
            "status": consent_display_status(c),
            "scope": c.record_scope,
            "priority": consent_priority(c),
        }
    
    result = []
    for p in patients:
        consent_info = consent_map.get(p.id, {})
        result.append({
            "id": p.id,
            "full_name": p.full_name,
            "gender": p.gender,
            "birth_date": str(p.birth_date)[:10] if p.birth_date else "",
            "status": consent_info.get("status", "NONE"),
            "scope": consent_info.get("scope", "")
        })
    
    return {"patients": result}


@router.post("/patients/{patient_id}/records")
def add_patient_record(
    patient_id: int,
    payload: MedicalRecordUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    
    # 检查是否有有效授权（DEFAULT 或 EXTRA 都可以）
    valid_consent = get_valid_consent(
        db,
        patient_id=patient_id,
        doctor_user_id=current_user.id,
    )
    if valid_consent is None:
        write_audit_log(
            db,
            action="DOCTOR_ADD_RECORD_DENIED",
            actor=current_user,
            target_type="patient",
            target_id=patient_id,
            doctor_id=current_user.id,
            patient_id=patient_id,
            outcome="DENIED",
            detail="Doctor add record denied: no active consent",
            **request_audit_context(request),
        )
        db.commit()
        raise HTTPException(status_code=403, detail="No access permission")
    
    from app.models.medical_record import MedicalRecord
    from app.services.crypto_service import encrypt_record_json
    
    # 验证患者存在
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    try:
        encrypted_data, nonce = encrypt_record_json(payload.record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to encrypt medical record") from exc
    
    new_record = MedicalRecord(
        patient_id=patient_id,
        source="DOCTOR",
        record_type="DOCTOR_ADDED",
        encrypted_data=encrypted_data,
        nonce=nonce,
        updated_by_doctor_id=current_user.id,
        created_at=now_beijing(),
        updated_at=now_beijing()
    )
    db.add(new_record)
    db.flush()
    
    write_audit_log(
        db,
        action="DOCTOR_ADD_RECORD",
        actor=current_user,
        target_type="medical_record",
        target_id=new_record.id,
        doctor_id=current_user.id,
        patient_id=patient_id,
        consent_id=valid_consent.id,
        record_scope=valid_consent.record_scope,
        outcome="SUCCESS",
        detail="Doctor added new medical record",
        **request_audit_context(request),
    )
    db.commit()
    
    return {"record_id": new_record.id, "patient_id": patient_id, "message": "Medical record added successfully"}