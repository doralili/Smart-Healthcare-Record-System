from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, require_roles
from app.core.timezone import now_beijing
from app.models.user import User
from app.models.doctor import Doctor
from app.models.consent import Consent
from app.models.patient import Patient
from app.schemas.doctor import AccessRequestCreate
from app.services.masking import mask_record_by_scope
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/api/doctor", tags=["医生业务模块"])


def ensure_doctor_approved(db: Session, user: User) -> None:
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if doctor is None or not doctor.verified:
        raise HTTPException(
            status_code=403,
            detail="Doctor account is pending admin approval",
        )


def consent_display_status(consent: Consent) -> str:
    if (
        consent.status == "ACTIVE"
        and consent.end_time is not None
        and consent.end_time <= now_beijing()
    ):
        return "EXPIRED"
    return consent.status

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
    
    result = []
    for consent in consents:
        # Get patient info
        patient = db.query(Patient).filter(Patient.id == consent.patient_id).first()
        if patient:
            result.append({
                "id": patient.id,
                "full_name": patient.full_name,
                "gender": patient.gender,
                "birth_date": patient.birth_date,
                "phone": patient.phone,
                "address": patient.address,
                "consent_status": consent_display_status(consent),      # ACTIVE, PENDING, REVOKED, EXPIRED
                "scope": consent.record_scope,         # DEFAULT, EXTRA
                "consent_id": consent.id
            })
    
    return {"patient_list": result}

# 提交额外病历访问申请
@router.post("/access-requests")
def submit_access_request(
    info: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    # 查找是否已存在记录
    existing = db.query(Consent).filter(
        Consent.patient_id == info.patient_id,
        Consent.doctor_id == current_user.id
    ).first()
    
    if existing:
        # 已有记录：更新状态和范围
        if existing.status == "ACTIVE":
            # 从 DEFAULT 升级到 EXTRA
            existing.record_scope = info.record_scope
            existing.status = "PENDING"
            existing.request_reason = info.reason
        elif existing.status == "PENDING":
            raise HTTPException(status_code=400, detail="Already has a pending request")
        elif existing.status == "REVOKED":
            # 重新申请
            existing.record_scope = info.record_scope
            existing.status = "PENDING"
            existing.request_reason = info.reason
        else:
            raise HTTPException(status_code=400, detail="Invalid status")
        consent_for_log = existing
    else:
        # 无记录：创建新记录
        new_consent = Consent(
            patient_id=info.patient_id,
            doctor_id=current_user.id,
            record_scope=info.record_scope,
            status="PENDING",
            request_reason=info.reason,
            consent_source="EXPLICIT_REQUEST"
        )
        db.add(new_consent)
        db.flush()
        consent_for_log = new_consent
    
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
    )
    db.commit()
    return {"msg": "Access request submitted, waiting for patient approval"}
# 查看脱敏后患者病历
# 场景1/3/5：查看脱敏病历 + 权限校验 + 日志记录
@router.get("/patients/{patient_id}/records")
def get_patient_mask_record(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_roles("DOCTOR"))
):
    ensure_doctor_approved(db, current_user)
    from app.models.medical_record import MedicalRecord
    from app.services.crypto_service import decrypt_record_json
    from app.models.access_log import AccessLog
    from app.models.patient import Patient
    
    # 1. 检查有效授权
    valid_consent = db.query(Consent).filter(
        Consent.patient_id == patient_id,
        Consent.doctor_id == current_user.id,
        Consent.status == "ACTIVE",
        Consent.end_time.isnot(None),
        Consent.end_time > now_beijing(),
    ).first()

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
    )
    db.commit()

    # 3. 无权限拒绝
    if not valid_consent:
        raise HTTPException(status_code=403, detail="No access permission or authorization expired")

    # 4. 获取患者基本信息（从 patients 表）
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # 5. 查询并解密病历
    medical_record = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient_id
    ).order_by(MedicalRecord.created_at.desc()).first()
    
    clinical_data = {}
    if medical_record:
        try:
            clinical_data = decrypt_record_json(medical_record.encrypted_data, medical_record.nonce)
        except Exception as e:
            print(f"Decryption failed: {e}")
            clinical_data = {}
    
    # 6. 手机号脱敏函数
    def mask_phone(phone):
        if not phone:
            return ""
        phone_str = str(phone)
        if len(phone_str) >= 7:
            return phone_str[:3] + "****" + phone_str[-4:]
        return phone_str
    
    # 7. 提取诊断列表
    conditions = clinical_data.get("conditions", [])
    diagnoses_list = []
    for cond in conditions:
        diagnoses_list.append({
            "name": cond.get("code", ""),
            "status": cond.get("clinical_status", "active"),
            "date": cond.get("recorded_date", "")[:10] if cond.get("recorded_date") else ""
        })
    
    # 8. 提取用药列表
    medications = clinical_data.get("medications", [])
    medications_list = []
    for med in medications:
        medications_list.append({
            "name": med.get("code", ""),
            "start_date": med.get("start_date", "")[:10] if med.get("start_date") else "",
            "stop_date": med.get("stop_date", "")[:10] if med.get("stop_date") else ""
        })
    
    # 9. 提取检查结果
    observations = clinical_data.get("observations", [])
    observations_list = []
    for obs in observations:
        observations_list.append({
            "test_name": obs.get("code", ""),
            "value": obs.get("value", ""),
            "date": obs.get("recorded_date", "")[:10] if obs.get("recorded_date") else ""
        })
    
    # 10. 提取手术/操作
    procedures = clinical_data.get("procedures", [])
    procedures_list = []
    for proc in procedures:
        procedures_list.append({
            "name": proc.get("code", ""),
            "date": proc.get("performed_date", "")[:10] if proc.get("performed_date") else ""
        })
    
    # 11. 按授权范围脱敏
    scope = valid_consent.record_scope
    
    if scope == "DEFAULT":
        # 默认范围：基本信息 + 诊断列表
        result = {
            "name": patient.full_name,
            "gender": patient.gender,
            "phone": mask_phone(patient.phone),
            "address": patient.address,
            "birth_date": str(patient.birth_date) if patient.birth_date else "",
            "visits": len(clinical_data.get("encounters", [])),
            "diagnoses": len(conditions),
            "lab_results": "Limited - apply full access to view",
            "medications": "Limited - apply full access to view",
            "procedures": "Limited - apply full access to view",
            "diagnosis_list": diagnoses_list,
            "message": "Default scope - only basic info and diagnoses are shown"
        }
    else:
        # 额外授权范围：完整信息
        result = {
            "name": patient.full_name,
            "gender": patient.gender,
            "phone": patient.phone,
            "address": patient.address,
            "birth_date": str(patient.birth_date) if patient.birth_date else "",
            "visits": len(clinical_data.get("encounters", [])),
            "diagnoses": len(conditions),
            "lab_results": observations_list,
            "medications": medications_list,
            "procedures": procedures_list,
            "diagnosis_list": diagnoses_list,
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
        consent_map[c.patient_id] = {
            "status": consent_display_status(c),
            "scope": c.record_scope
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
