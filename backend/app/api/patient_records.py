from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.deps import require_roles
from app.core.timezone import BEIJING_TZ, now_beijing
from app.db.session import get_db
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.consent import Consent
from app.models.doctor import Doctor
from app.models.user import User
from app.services.clinical_records import filter_related_clinical_records, normalize_clinical_record_links
from app.services.crypto_service import MedicalRecordCryptoError, decrypt_record_json
from app.services.audit_service import request_audit_context, write_audit_log


router = APIRouter(prefix="/api/patient/me/records", tags=["patient-records"])
CONSENT_VALID_DAYS = 14


class SelectDoctorRequest(BaseModel):
    doctor_user_id: int


def get_current_patient(db: Session, current_user: User) -> Patient:
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


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


def consent_priority(consent: Consent) -> tuple[int, int]:
    status_rank = {
        "ACTIVE": 4,
        "PENDING": 3,
        "REJECTED": 2,
        "REVOKED": 1,
        "EXPIRED": 0,
    }.get(consent_display_status(consent), 0)
    scope_rank = {"EXTRA": 2, "DEFAULT": 1}.get(consent.record_scope, 0)
    return status_rank, scope_rank


def has_active_full_consent(db: Session, *, patient_id: int, doctor_user_id: int) -> bool:
    return db.query(Consent).filter(
        Consent.patient_id == patient_id,
        Consent.doctor_id == doctor_user_id,
        Consent.record_scope == "EXTRA",
        Consent.status == "ACTIVE",
        Consent.end_time.isnot(None),
        Consent.end_time > now_beijing(),
    ).first() is not None


# ========== 具体路径的路由（必须放在动态路由之前） ==========

def has_active_default_consent(db: Session, *, patient_id: int, doctor_user_id: int) -> bool:
    return db.query(Consent).filter(
        Consent.patient_id == patient_id,
        Consent.doctor_id == doctor_user_id,
        Consent.record_scope == "DEFAULT",
        Consent.status == "ACTIVE",
        Consent.end_time.isnot(None),
        Consent.end_time > now_beijing(),
    ).first() is not None


def best_consents_by_doctor(consents: list[Consent]) -> dict[int, Consent]:
    result: dict[int, Consent] = {}
    for consent in consents:
        current_best = result.get(consent.doctor_id)
        if current_best is None or consent_priority(consent) > consent_priority(current_best):
            result[consent.doctor_id] = consent
    return result


def is_placeholder_doctor_name(value: str | None) -> bool:
    normalized = str(value or "").strip().casefold().replace(" ", "")
    return normalized in {"", "norecord", "notrecorded", "unknown", "none", "null"}


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
    if doctor is not None and doctor.name:
        display_name = doctor.name
    else:
        display_name = user.username
    return "" if is_placeholder_doctor_name(display_name) else display_name


def normalize_department(value: str | None) -> str:
    return str(value or "").strip().casefold()


def get_doctor_display_name(user: User, doctor: Doctor | None) -> str:
    if doctor is not None and doctor.name:
        display_name = doctor.name
    else:
        display_name = user.username
    return "" if is_placeholder_doctor_name(display_name) else display_name


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
    doctor_name = record_doctor_name
    if (
        allow_department_fallback
        and is_placeholder_doctor_name(doctor_name)
        and department_doctor_map is not None
    ):
        doctor_name = get_doctor_name_by_department(
            department_doctor_map,
            str(item.get("department") or ""),
        )

    if doctor_name and not is_placeholder_doctor_name(doctor_name):
        item_copy["doctor_name"] = doctor_name
        item_copy["doctor"] = doctor_name
    else:
        item_copy.pop("doctor_name", None)
        if is_placeholder_doctor_name(str(item_copy.get("doctor") or "")):
            item_copy.pop("doctor", None)
    return item_copy


@router.get("/combined")
def get_my_combined_records(
    request: Request,
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    """获取患者所有病历的合并数据，包含医生信息"""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    
    medical_records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient.id
    ).order_by(MedicalRecord.created_at.desc()).all()
    
    # 合并所有病历数据
    all_conditions = []
    all_medications = []
    all_observations = []
    all_procedures = []
    all_encounters = []
    
    # 医生信息缓存
    doctor_cache = {}
    department_doctor_map = get_department_doctor_map(db)
    
    for record in medical_records:
        try:
            clinical_data = filter_related_clinical_records(
                normalize_clinical_record_links(
                    decrypt_record_json(record.encrypted_data, record.nonce)
                )
            )
            
            # 获取医生信息
            doctor_name = None
            if record.updated_by_doctor_id:
                if record.updated_by_doctor_id not in doctor_cache:
                    doctor_cache[record.updated_by_doctor_id] = get_doctor_display_name_by_user_id(
                        db,
                        record.updated_by_doctor_id,
                    )
                doctor_name = doctor_cache[record.updated_by_doctor_id]
            
            # 处理诊断，添加医生信息
            for cond in clinical_data.get("conditions", []):
                all_conditions.append(
                    apply_doctor_name(
                        cond,
                        record_doctor_name=doctor_name,
                        department_doctor_map=department_doctor_map,
                    )
                )
            
            # 处理用药
            for med in clinical_data.get("medications", []):
                all_medications.append(
                    apply_doctor_name(
                        med,
                        record_doctor_name=doctor_name,
                        department_doctor_map=department_doctor_map,
                        allow_department_fallback=False,
                    )
                )
            
            # 处理检查结果
            for obs in clinical_data.get("observations", []):
                all_observations.append(
                    apply_doctor_name(
                        obs,
                        record_doctor_name=doctor_name,
                        department_doctor_map=department_doctor_map,
                        allow_department_fallback=False,
                    )
                )
            
            # 处理手术
            for proc in clinical_data.get("procedures", []):
                all_procedures.append(
                    apply_doctor_name(
                        proc,
                        record_doctor_name=doctor_name,
                        department_doctor_map=department_doctor_map,
                        allow_department_fallback=False,
                    )
                )
            
            # 处理就诊
            for enc in clinical_data.get("encounters", []):
                all_encounters.append(
                    apply_doctor_name(
                        enc,
                        record_doctor_name=doctor_name,
                        department_doctor_map=department_doctor_map,
                        allow_department_fallback=False,
                    )
                )
                
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
    
    all_conditions = dedupe_by_id(all_conditions)
    all_medications = dedupe_by_id(all_medications)
    all_observations = dedupe_by_id(all_observations)
    all_procedures = dedupe_by_id(all_procedures)
    all_encounters = dedupe_by_id(all_encounters, key="id")
    
    write_audit_log(
        db,
        action="PATIENT_VIEW_OWN_RECORD",
        actor=current_user,
        target_type="patient",
        target_id=patient.id,
        patient_id=patient.id,
        outcome="SUCCESS",
        detail="Patient viewed combined medical records",
        **request_audit_context(request),
    )
    db.commit()
    
    latest_record = medical_records[0] if medical_records else None

    return {
        "id": latest_record.id if latest_record else None,
        "patient_id": patient.id,
        "source": "COMBINED",
        "record_type": "COMBINED",
        "created_at": latest_record.created_at if latest_record else now_beijing(),
        "record_count": len(medical_records),
        "latest_record_id": latest_record.id if latest_record else None,
        "latest_record_created_at": latest_record.created_at if latest_record else None,
        "patient": {
            "id": patient.id,
            "synthea_patient_id": patient.synthea_patient_id,
            "full_name": patient.full_name,
            "gender": patient.gender,
            "birth_date": patient.birth_date,
            "phone": patient.phone,
            "address": patient.address,
            "created_at": patient.created_at,
        },
        "record": {
            "conditions": all_conditions,
            "medications": all_medications,
            "observations": all_observations,
            "procedures": all_procedures,
            "encounters": all_encounters
        }
    }


@router.get("/available-doctors")
def get_available_doctors(
    department: str = "",
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    patient = get_current_patient(db, current_user)

    department_filter = department.strip()

    doctor_query = (
        db.query(User, Doctor)
        .join(Doctor, Doctor.user_id == User.id)
        .filter(User.role == "DOCTOR")
        .filter(User.status == "ACTIVE")
        .filter(Doctor.verified.is_(True))
    )

    if department_filter:
        doctor_query = doctor_query.filter(Doctor.department.ilike(f"%{department_filter}%"))

    doctors = doctor_query.order_by(Doctor.department.asc(), Doctor.name.asc()).all()

    consents = (
        db.query(Consent)
        .filter(Consent.patient_id == patient.id)
        .filter(Consent.record_scope.in_(["DEFAULT", "EXTRA"]))
        .all()
    )
    consent_map = best_consents_by_doctor(consents)
    default_consent_map = best_consents_by_doctor(
        [consent for consent in consents if consent.record_scope == "DEFAULT"]
    )

    def doctor_payload(user: User, doctor: Doctor) -> dict:
        best_consent = consent_map.get(user.id)
        default_consent = default_consent_map.get(user.id)
        access_status = consent_display_status(best_consent) if best_consent else "NONE"
        access_scope = best_consent.record_scope if best_consent else None
        has_blocking_access = access_status == "ACTIVE" and access_scope in {"DEFAULT", "EXTRA"}

        return {
            "doctor_user_id": user.id,
            "username": user.username,
            "name": doctor.name,
            "department": doctor.department,
            "license_no": doctor.license_no,
            "default_consent_status": consent_display_status(default_consent)
            if default_consent
            else "NONE",
            "default_consent_id": default_consent.id if default_consent else None,
            "default_consent_end_time": default_consent.end_time if default_consent else None,
            "access_status": access_status,
            "access_scope": access_scope,
            "access_consent_id": best_consent.id if best_consent else None,
            "access_end_time": best_consent.end_time if best_consent else None,
            "can_select_default": not has_blocking_access,
        }

    return {
        "doctors": [doctor_payload(user, doctor) for user, doctor in doctors],
    }


@router.post("/default-doctors")
def select_default_doctor(
    payload: SelectDoctorRequest,
    request: Request,
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    patient = get_current_patient(db, current_user)

    doctor_user = db.get(User, payload.doctor_user_id)
    if doctor_user is None or doctor_user.role != "DOCTOR":
        raise HTTPException(status_code=404, detail="Doctor user not found")
    if doctor_user.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Doctor account is not active")

    doctor_profile = db.query(Doctor).filter(Doctor.user_id == doctor_user.id).first()
    if doctor_profile is None or not doctor_profile.verified:
        raise HTTPException(status_code=400, detail="Doctor is not approved")

    if has_active_full_consent(db, patient_id=patient.id, doctor_user_id=doctor_user.id):
        raise HTTPException(
            status_code=400,
            detail="Full access is already active; default access is covered",
        )
    if has_active_default_consent(db, patient_id=patient.id, doctor_user_id=doctor_user.id):
        raise HTTPException(
            status_code=400,
            detail="Default access is already active for this doctor",
        )

    consent = (
        db.query(Consent)
        .filter(Consent.patient_id == patient.id)
        .filter(Consent.doctor_id == doctor_user.id)
        .filter(Consent.record_scope == "DEFAULT")
        .first()
    )

    now = now_beijing()
    expires_at = now + timedelta(days=CONSENT_VALID_DAYS)
    if consent is None:
        consent = Consent(
            patient_id=patient.id,
            doctor_id=doctor_user.id,
            record_scope="DEFAULT",
            permission="READ",
            status="ACTIVE",
            consent_source="PATIENT_SELECTED_DOCTOR",
            default_scope="DEFAULT_CLINICAL",
            start_time=now,
            end_time=expires_at,
            auto_granted_at=now,
            approved_at=now,
        )
        db.add(consent)
        db.flush()
    else:
        consent.permission = "READ"
        consent.status = "ACTIVE"
        consent.consent_source = "PATIENT_SELECTED_DOCTOR"
        consent.default_scope = "DEFAULT_CLINICAL"
        consent.start_time = now
        consent.end_time = expires_at
        consent.auto_granted_at = consent.auto_granted_at or now
        consent.approved_at = now
        consent.revoked_at = None

    write_audit_log(
        db,
        action="PATIENT_SELECT_DEFAULT_DOCTOR",
        actor=current_user,
        target_type="doctor",
        target_id=doctor_user.id,
        doctor_id=doctor_user.id,
        patient_id=patient.id,
        consent_id=consent.id,
        record_scope="DEFAULT",
        outcome="SUCCESS",
        detail="Patient selected doctor for default clinical access",
        **request_audit_context(request),
    )
    db.commit()

    return {
        "consent_id": consent.id,
        "doctor_user_id": doctor_user.id,
        "patient_id": patient.id,
        "status": consent.status,
        "record_scope": consent.record_scope,
        "end_time": consent.end_time,
    }


@router.get("/pending-consents")
def get_pending_consents(
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    """患者查看待审批的医生授权申请"""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        return {"pending_consents": []}
    
    pending = db.query(Consent).filter(
        Consent.patient_id == patient.id,
        Consent.status == "PENDING"
    ).all()
    
    result = []
    for c in pending:
        result.append({
            "consent_id": c.id,
            "doctor_name": get_doctor_display_name_by_user_id(db, c.doctor_id),
            "record_scope": c.record_scope,
            "request_reason": c.request_reason,
            "created_at": c.created_at
        })
    
    return {"pending_consents": result}


@router.get("/my-doctors")
def get_my_doctors(
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    """患者查看已授权的医生列表"""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        return {"doctors": []}
    
    active_consents = db.query(Consent).filter(
        Consent.patient_id == patient.id,
        Consent.status == "ACTIVE"
    ).all()

    best_consents_by_doctor: dict[int, Consent] = {}
    for consent in active_consents:
        if consent_display_status(consent) != "ACTIVE":
            continue
        current_best = best_consents_by_doctor.get(consent.doctor_id)
        if current_best is None or consent_priority(consent) > consent_priority(current_best):
            best_consents_by_doctor[consent.doctor_id] = consent
    
    result = []
    for c in best_consents_by_doctor.values():
        result.append({
            "consent_id": c.id,
            "doctor_name": get_doctor_display_name_by_user_id(db, c.doctor_id),
            "record_scope": c.record_scope,
            "granted_at": c.approved_at or c.created_at
        })
    
    return {"doctors": result}


@router.post("/consents/{consent_id}/approve")
def approve_consent(
    consent_id: int,
    request: Request,
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    """患者批准医生的授权申请"""
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient or consent.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="Not your consent")
    
    if consent.status != "PENDING":
        raise HTTPException(status_code=400, detail="Already processed")

    if consent.record_scope == "DEFAULT" and has_active_full_consent(
        db,
        patient_id=consent.patient_id,
        doctor_user_id=consent.doctor_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Full access is already active; default approval is not needed",
        )
    
    consent.status = "ACTIVE"
    now = now_beijing()
    consent.start_time = now
    consent.approved_at = now
    consent.end_time = now + timedelta(days=CONSENT_VALID_DAYS)

    if consent.record_scope == "EXTRA":
        db.query(Consent).filter(
            Consent.patient_id == consent.patient_id,
            Consent.doctor_id == consent.doctor_id,
            Consent.record_scope == "DEFAULT",
            Consent.status == "ACTIVE",
            Consent.id != consent.id,
        ).update(
            {
                "status": "REVOKED",
                "revoked_at": now,
            },
            synchronize_session=False,
        )
    write_audit_log(
        db,
        action="CONSENT_APPROVE",
        actor=current_user,
        target_type="consent",
        target_id=consent.id,
        doctor_id=consent.doctor_id,
        patient_id=consent.patient_id,
        consent_id=consent.id,
        record_scope=consent.record_scope,
        outcome="SUCCESS",
        detail="Patient approved doctor access request",
        **request_audit_context(request),
    )
    db.commit()
    
    return {"msg": "Access granted"}


@router.post("/consents/{consent_id}/reject")
def reject_consent(
    consent_id: int,
    request: Request,
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    """患者拒绝医生的授权申请"""
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient or consent.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="Not your consent")
    
    if consent.status != "PENDING":
        raise HTTPException(status_code=400, detail="Already processed")
    
    consent.status = "REJECTED"
    write_audit_log(
        db,
        action="CONSENT_REJECT",
        actor=current_user,
        target_type="consent",
        target_id=consent.id,
        doctor_id=consent.doctor_id,
        patient_id=consent.patient_id,
        consent_id=consent.id,
        record_scope=consent.record_scope,
        outcome="DENIED",
        detail="Patient rejected doctor access request",
        **request_audit_context(request),
    )
    db.commit()
    
    return {"msg": "Access denied"}


@router.post("/consents/{consent_id}/revoke")
def revoke_consent(
    consent_id: int,
    request: Request,
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    """患者撤销医生的访问权限"""
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient or consent.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="Not your consent")
    
    if consent.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Only active consent can be revoked")
    
    consent.status = "REVOKED"
    consent.revoked_at = now_beijing()
    write_audit_log(
        db,
        action="CONSENT_REVOKE",
        actor=current_user,
        target_type="consent",
        target_id=consent.id,
        doctor_id=consent.doctor_id,
        patient_id=consent.patient_id,
        consent_id=consent.id,
        record_scope=consent.record_scope,
        outcome="SUCCESS",
        detail="Patient revoked doctor access",
        **request_audit_context(request),
    )
    db.commit()
    
    return {"msg": "Access revoked"}


# ========== 动态路由（必须放在最后） ==========

@router.get("")
def list_my_records(
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    records = (
        db.query(MedicalRecord)
        .join(Patient, MedicalRecord.patient_id == Patient.id)
        .filter(Patient.user_id == current_user.id)
        .order_by(MedicalRecord.created_at.desc())
        .all()
    )

    return [
        {
            "id": record.id,
            "patient_id": record.patient_id,
            "source": record.source,
            "record_type": record.record_type,
            "created_at": record.created_at,
        }
        for record in records
    ]


@router.get("/{record_id}")
def get_my_record_detail(
    record_id: int,
    request: Request,
    current_user: User = Depends(require_roles("PATIENT")),
    db: Session = Depends(get_db),
):
    result = (
        db.query(MedicalRecord, Patient)
        .join(Patient, MedicalRecord.patient_id == Patient.id)
        .filter(MedicalRecord.id == record_id)
        .filter(Patient.user_id == current_user.id)
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found",
        )

    record, patient = result

    try:
        decrypted_record = filter_related_clinical_records(
            normalize_clinical_record_links(
                decrypt_record_json(record.encrypted_data, record.nonce)
            )
        )
    except MedicalRecordCryptoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt medical record",
        ) from exc

    record_doctor_name = None
    if record.updated_by_doctor_id:
        record_doctor_name = get_doctor_display_name_by_user_id(
            db,
            record.updated_by_doctor_id,
        )

    department_doctor_map = get_department_doctor_map(db)
    for key in ["conditions", "medications", "observations", "procedures", "encounters"]:
        decrypted_record[key] = [
            apply_doctor_name(
                item,
                record_doctor_name=record_doctor_name,
                department_doctor_map=department_doctor_map,
                allow_department_fallback=(key == "conditions"),
            )
            for item in decrypted_record.get(key, [])
            if isinstance(item, dict)
        ]

    write_audit_log(
        db,
        action="PATIENT_VIEW_OWN_RECORD",
        actor=current_user,
        target_type="medical_record",
        target_id=record.id,
        patient_id=patient.id,
        outcome="SUCCESS",
        detail="Patient viewed own medical record",
        **request_audit_context(request),
    )
    db.commit()

    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "source": record.source,
        "record_type": record.record_type,
        "created_at": record.created_at,
        "patient": {
            "id": patient.id,
            "synthea_patient_id": patient.synthea_patient_id,
            "full_name": patient.full_name,
            "gender": patient.gender,
            "birth_date": patient.birth_date,
            "phone": patient.phone,
            "address": patient.address,
            "created_at": patient.created_at,
        },
        "record": decrypted_record,
    }
