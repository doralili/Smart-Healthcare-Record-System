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
from app.services.clinical_records import filter_related_clinical_records, normalize_clinical_record_links
from app.services.audit_service import request_audit_context, write_audit_log
from app.services.crypto_service import encrypt_record_json
from app.services.record_watermark import embed_record_watermark

router = APIRouter(prefix="/api/doctor", tags=["医生业务模块"])


class MedicalRecordCreateRequest(BaseModel):
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


def is_placeholder_doctor_name(value: str | None) -> bool:
    normalized = str(value or "").strip().casefold().replace(" ", "")
    return normalized in {"", "norecord", "notrecorded", "unknown", "none", "null"}


def normalize_department(value: str | None) -> str:
    return str(value or "").strip().casefold()


def get_doctor_display_name(user: User, doctor: Doctor | None) -> str:
    if doctor is not None and doctor.name:
        display_name = doctor.name
    else:
        display_name = user.username
    return "" if is_placeholder_doctor_name(display_name) else display_name


def get_doctor_display_name_by_user_id(db: Session, user_id: int) -> str:
    result = (
        db.query(User, Doctor)
        .outerjoin(Doctor, Doctor.user_id == User.id)
        .filter(User.id == user_id)
        .first()
    )
    if result is None:
        return ""

    user, doctor = result
    return get_doctor_display_name(user, doctor)


def get_department_doctor_map(db: Session) -> dict[str, str]:
    rows = (
        db.query(User, Doctor)
        .join(Doctor, Doctor.user_id == User.id)
        .filter(User.role == "DOCTOR")
        .filter(User.status == "ACTIVE")
        .filter(Doctor.verified.is_(True))
        .order_by(Doctor.department.asc(), Doctor.name.asc())
        .all()
    )

    result: dict[str, str] = {}
    for user, doctor in rows:
        department_key = normalize_department(doctor.department)
        display_name = get_doctor_display_name(user, doctor)
        if department_key and display_name and department_key not in result:
            result[department_key] = display_name
    return result


def get_doctor_name_by_department(
    department_doctor_map: dict[str, str],
    department: str | None,
) -> str:
    departments = [
        normalize_department(item)
        for item in str(department or "").split(";")
        if normalize_department(item)
    ]

    for department_key in departments:
        doctor_name = department_doctor_map.get(department_key)
        if doctor_name:
            return doctor_name

    if not departments:
        return department_doctor_map.get(normalize_department("General Medicine"), "")

    return ""


def apply_doctor_name(
    item: dict,
    *,
    record_doctor_name: str | None,
    department_doctor_map: dict[str, str] | None = None,
    allow_department_fallback: bool = True,
) -> dict:
    item_copy = item.copy()
    doctor_name = record_doctor_name or item_copy.get("doctor_name") or item_copy.get("doctor")
    if (
        allow_department_fallback
        and is_placeholder_doctor_name(str(doctor_name or ""))
        and department_doctor_map is not None
    ):
        doctor_name = get_doctor_name_by_department(
            department_doctor_map,
            str(item.get("department") or ""),
        )

    if doctor_name and not is_placeholder_doctor_name(str(doctor_name)):
        item_copy["doctor_name"] = doctor_name
        item_copy["doctor"] = doctor_name
    else:
        item_copy.pop("doctor_name", None)
        if is_placeholder_doctor_name(str(item_copy.get("doctor") or "")):
            item_copy.pop("doctor", None)
    return item_copy


def enrich_clinical_data_doctor_names(
    clinical_data: dict[str, Any],
    *,
    record_doctor_name: str | None,
    department_doctor_map: dict[str, str],
) -> dict[str, Any]:
    enriched = dict(clinical_data)

    for key in ["conditions", "medications", "observations", "procedures", "encounters"]:
        allow_department_fallback = key == "conditions"
        enriched_items = []
        for item in enriched.get(key, []):
            if isinstance(item, dict):
                enriched_items.append(
                    apply_doctor_name(
                        item,
                        record_doctor_name=record_doctor_name,
                        department_doctor_map=department_doctor_map,
                        allow_department_fallback=allow_department_fallback,
                    )
                )
        enriched[key] = enriched_items

    for condition in enriched.get("conditions", []):
        if not isinstance(condition, dict):
            continue
        condition_doctor_name = condition.get("doctor_name") or condition.get("doctor")
        for related_key in [
            "related_encounters",
            "related_medications",
            "related_observations",
            "related_procedures",
        ]:
            condition[related_key] = [
                apply_doctor_name(
                    item,
                    record_doctor_name=str(condition_doctor_name or record_doctor_name or ""),
                    department_doctor_map=department_doctor_map,
                    allow_department_fallback=False,
                )
                for item in condition.get(related_key, [])
                if isinstance(item, dict)
            ]

    return enriched


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
    fallback_record_id = medical_records[0].id if medical_records else None
    doctor_cache: dict[int, str] = {}
    department_doctor_map = get_department_doctor_map(db)
    
    for record in medical_records:
        try:
            record_doctor_name = None
            if record.updated_by_doctor_id:
                if record.updated_by_doctor_id not in doctor_cache:
                    doctor_cache[record.updated_by_doctor_id] = get_doctor_display_name_by_user_id(
                        db,
                        record.updated_by_doctor_id,
                    )
                record_doctor_name = doctor_cache[record.updated_by_doctor_id]

            clinical_data = filter_related_clinical_records(
                normalize_clinical_record_links(
                    decrypt_record_json(record.encrypted_data, record.nonce)
                )
            )
            clinical_data = enrich_clinical_data_doctor_names(
                clinical_data,
                record_doctor_name=record_doctor_name,
                department_doctor_map=department_doctor_map,
            )
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

    if latest_record_id is None:
        latest_record_id = fallback_record_id
    
    # 构建 encounters 字典，方便按 encounter_id 查找就诊信息
    encounters_map = {}
    for enc in all_encounters:
        enc_id = enc.get("id")
        if enc_id:
            encounters_map[enc_id] = enc
    
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
    
    # 8. 构建诊断列表（带 related_encounters，包含医生信息）
    def build_diagnosis_list(conds, encounters_map):
        """构建诊断列表，可选地关联就诊信息"""
        result = []

        def encounter_payload(enc, cond):
            return {
                "id": enc.get("id"),
                "type": enc.get("type", ""),
                "class": enc.get("class", ""),
                "status": enc.get("status", ""),
                "start": enc.get("start", ""),
                "doctor_name": enc.get("doctor_name") or cond.get("doctor_name", ""),
                "doctor": enc.get("doctor") or cond.get("doctor", ""),
                "doctor_department": enc.get("doctor_department", "")
            }

        for cond in conds:
            encounter_id = cond.get("encounter_id")
            related_encounters = [
                encounter_payload(enc, cond)
                for enc in cond.get("related_encounters", [])
                if isinstance(enc, dict)
            ]
            
            # 如果有 encounter_id，从 encounters_map 中获取对应的就诊信息
            if not related_encounters and encounter_id and encounter_id in encounters_map:
                enc = encounters_map[encounter_id]
                related_encounters = [encounter_payload(enc, cond)]
            
            result.append({
                "name": cond.get("code", ""),
                "department": cond.get("department", "Not Classified"),
                "status": cond.get("clinical_status", "active"),
                "date": cond.get("recorded_date", "")[:10] if cond.get("recorded_date") else "",
                "encounter_id": encounter_id,
                "doctor_name": cond.get("doctor_name", ""),
                "doctor": cond.get("doctor", ""),
                "related_encounters": related_encounters,
                "related_observations": cond.get("related_observations", []),
                "related_medications": cond.get("related_medications", []),
                "related_procedures": cond.get("related_procedures", [])
            })
        return result

    def collect_related_items(conds, related_key):
        related_items = []
        seen = set()
        for cond in conds:
            for item in cond.get(related_key, []):
                if not isinstance(item, dict):
                    continue
                item_key = str(item.get("id") or id(item))
                if item_key in seen:
                    continue
                seen.add(item_key)
                related_items.append(item)
        return related_items
    
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
        filtered_observations = collect_related_items(filtered_conditions, "related_observations")
        filtered_medications = collect_related_items(filtered_conditions, "related_medications")
        filtered_procedures = collect_related_items(filtered_conditions, "related_procedures")
        
        result = {
            "record_id": latest_record_id,
            "name": patient.full_name,
            "gender": patient.gender,
            "phone": mask_phone(patient.phone),
            "address": mask_address(patient.address),
            "birth_date": str(patient.birth_date) if patient.birth_date else "",
            "visits": len(all_encounters),
            "diagnoses": len(filtered_conditions),
            "lab_results": build_observations_list(filtered_observations),
            "medications": build_medications_list(filtered_medications),
            "procedures": build_procedures_list(filtered_procedures),
            "diagnosis_list": build_diagnosis_list(filtered_conditions, encounters_map),
            "updated_at": latest_updated_at,
            "updated_by_doctor_id": latest_updated_by,
            "record_scope": scope,
            "message": (
                "Default scope - records related to diagnoses from the last year "
                f"({len(filtered_conditions)} diagnoses found)"
            )
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
            "diagnosis_list": build_diagnosis_list(all_conditions, encounters_map),
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
    payload: MedicalRecordCreateRequest,
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
    
    # 验证患者存在
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # 获取医生信息，自动添加到记录中
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    doctor_name = doctor.name if doctor else current_user.username
    doctor_department = doctor.department if doctor else ""
    
    # 处理记录数据，自动添加医生信息
    record_data = normalize_clinical_record_links(payload.record)
    
    # 为所有 encounters 添加医生信息
    for encounter in record_data.get("encounters", []):
        if "doctor_name" not in encounter or not encounter["doctor_name"]:
            encounter["doctor_name"] = doctor_name
        if "doctor_department" not in encounter or not encounter["doctor_department"]:
            encounter["doctor_department"] = doctor_department
    
    # 为所有 conditions 添加医生信息
    for condition in record_data.get("conditions", []):
        if "doctor_name" not in condition or not condition["doctor_name"]:
            condition["doctor_name"] = doctor_name
        if "doctor_department" not in condition or not condition["doctor_department"]:
            condition["doctor_department"] = doctor_department
    
    # 为所有 observations 添加医生信息
    for observation in record_data.get("observations", []):
        if "doctor_name" not in observation or not observation["doctor_name"]:
            observation["doctor_name"] = doctor_name
        if "doctor_department" not in observation or not observation["doctor_department"]:
            observation["doctor_department"] = doctor_department
    
    # 为所有 medications 添加医生信息
    for medication in record_data.get("medications", []):
        if "doctor_name" not in medication or not medication["doctor_name"]:
            medication["doctor_name"] = doctor_name
        if "doctor_department" not in medication or not medication["doctor_department"]:
            medication["doctor_department"] = doctor_department
    
    # 为所有 procedures 添加医生信息
    for procedure in record_data.get("procedures", []):
        if "doctor_name" not in procedure or not procedure["doctor_name"]:
            procedure["doctor_name"] = doctor_name
        if "doctor_department" not in procedure or not procedure["doctor_department"]:
            procedure["doctor_department"] = doctor_department
    
    created_at = now_beijing()
    record_data = embed_record_watermark(
        record_data,
        patient_id=patient_id,
        doctor_id=current_user.id,
        issued_at=created_at.isoformat(),
    )

    try:
        encrypted_data, nonce = encrypt_record_json(record_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to encrypt medical record") from exc
    
    new_record = MedicalRecord(
        patient_id=patient_id,
        source="DOCTOR",
        record_type="DOCTOR_ADDED",
        encrypted_data=encrypted_data,
        nonce=nonce,
        updated_by_doctor_id=current_user.id,
        created_at=created_at,
        updated_at=created_at
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
