from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, require_roles
from app.core.timezone import now_beijing
from app.models.user import User
from app.models.doctor import Doctor
from app.models.consent import Consent
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.doctor import AccessRequestCreate
from app.services.clinical_records import filter_related_clinical_records, normalize_clinical_record_links
from app.services.audit_service import request_audit_context, write_audit_log
from app.services.crypto_service import encrypt_record_json
from app.services.record_watermark import embed_record_watermark
from app.services.consent_access import consent_display_status, consent_priority
from app.services.doctor_display import (
    get_department_doctor_map,
    get_doctor_display_name_by_user_id,
)
from app.services.record_presentation import (
    add_doctor_identity_to_record,
    build_diagnosis_list,
    build_medications_list,
    build_observations_list,
    build_procedures_list,
    collect_related_items,
    dedupe_by_id,
    enrich_clinical_data_doctor_names,
    filter_records_by_date,
    mask_address,
    mask_phone,
)

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


class MedicalRecordCreateRequest(BaseModel):
    record: dict[str, Any]


def ensure_doctor_approved(db: Session, user: User) -> None:
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if doctor is None or not doctor.verified:
        raise HTTPException(
            status_code=403,
            detail="Doctor account is pending admin approval",
        )


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

# 鑾峰彇鍚嶄笅鎺堟潈鎮ｈ€呭垪琛?
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

# 鎻愪氦棰濆鐥呭巻璁块棶鐢宠
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

# 鏌ョ湅鑴辨晱鍚庢偅鑰呯梾鍘?
# 鍦烘櫙1/3/5锛氭煡鐪嬭劚鏁忕梾鍘?+ 鏉冮檺鏍￠獙 + 鏃ュ織璁板綍
@router.get("/patients/{patient_id}/records")
def get_patient_mask_record(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    from app.models.medical_record import MedicalRecord
    from app.services.crypto_service import decrypt_record_json
    from app.models.access_log import AccessLog
    from app.models.patient import Patient
    
    # 1. 妫€鏌ユ湁鏁堟巿鏉?
    valid_consent = get_valid_consent(
        db,
        patient_id=patient_id,
        doctor_user_id=current_user.id,
    )

    # 2. 璁板綍瀹¤鏃ュ織
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

    # 3. 鏃犳潈闄愭嫆缁?
    if not valid_consent:
        raise HTTPException(status_code=403, detail="No access permission or authorization expired")

    # 4. 鑾峰彇鎮ｈ€呭熀鏈俊鎭?
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # 5. 鏌ヨ骞惰В瀵嗘墍鏈夌梾鍘嗭紙涓嶅彧鏄渶鏂扮殑涓€鏉★級
    medical_records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient_id
    ).order_by(MedicalRecord.created_at.desc()).all()
    
    # 鍚堝苟鎵€鏈夌梾鍘嗘暟鎹?
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
            
            # 璁板綍鏈€鏂版洿鏂扮殑淇℃伅
            if record.updated_at and (latest_updated_at is None or record.updated_at > latest_updated_at):
                latest_updated_at = record.updated_at
                latest_updated_by = record.updated_by_doctor_id
                latest_record_id = record.id
        except Exception as e:
            print(f"Decryption failed for record {record.id}: {e}")
            continue

    if latest_record_id is None:
        latest_record_id = fallback_record_id
    
    encounters_map = {}
    for enc in all_encounters:
        enc_id = enc.get("id")
        if enc_id:
            encounters_map[enc_id] = enc

    all_conditions = dedupe_by_id(all_conditions)
    all_medications = dedupe_by_id(all_medications)
    all_observations = dedupe_by_id(all_observations)
    all_procedures = dedupe_by_id(all_procedures)
    all_encounters = dedupe_by_id(all_encounters, key="id")

    scope = valid_consent.record_scope
    if scope == "DEFAULT":
        # Default access shows only recent diagnosis-related records.
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
        # Full access shows all available records.
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
    
    # 鑾峰彇鍖荤敓鎵€鏈夌殑鎺堟潈璁板綍
    existing_consents = db.query(Consent).filter(
        Consent.doctor_id == current_user.id
    ).all()
    
    # 鍒涘缓 patient_id -> 鎺堟潈淇℃伅鐨勬槧灏?
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
    
    # 妫€鏌ユ槸鍚︽湁鏈夋晥鎺堟潈锛圖EFAULT 鎴?EXTRA 閮藉彲浠ワ級
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
    
    # 楠岃瘉鎮ｈ€呭瓨鍦?
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # 鑾峰彇鍖荤敓淇℃伅锛岃嚜鍔ㄦ坊鍔犲埌璁板綍涓?
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    doctor_name = doctor.name if doctor else current_user.username
    doctor_department = doctor.department if doctor else ""
    
    record_data = normalize_clinical_record_links(payload.record)
    record_data = add_doctor_identity_to_record(
        record_data,
        doctor_name=doctor_name,
        doctor_department=doctor_department,
    )
    
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
