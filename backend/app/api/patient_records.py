from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.consent import Consent
from app.models.user import User
from app.services.crypto_service import MedicalRecordCryptoError, decrypt_record_json
from app.services.audit_service import write_audit_log


router = APIRouter(prefix="/api/patient/me/records", tags=["patient-records"])

# ========== 具体路径的路由（必须放在动态路由之前） ==========

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
        doctor = db.query(User).filter(User.id == c.doctor_id).first()
        result.append({
            "consent_id": c.id,
            "doctor_name": doctor.username if doctor else "Unknown",
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
    
    result = []
    for c in active_consents:
        doctor = db.query(User).filter(User.id == c.doctor_id).first()
        result.append({
            "consent_id": c.id,
            "doctor_name": doctor.username if doctor else "Unknown",
            "record_scope": c.record_scope,
            "granted_at": c.approved_at or c.created_at
        })
    
    return {"doctors": result}


@router.post("/consents/{consent_id}/approve")
def approve_consent(
    consent_id: int,
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
    
    consent.status = "ACTIVE"
    consent.approved_at = datetime.now()
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
    )
    db.commit()
    
    return {"msg": "Access granted"}


@router.post("/consents/{consent_id}/reject")
def reject_consent(
    consent_id: int,
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
    )
    db.commit()
    
    return {"msg": "Access denied"}


@router.post("/consents/{consent_id}/revoke")
def revoke_consent(
    consent_id: int,
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
    consent.revoked_at = datetime.now()
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
        decrypted_record = decrypt_record_json(record.encrypted_data, record.nonce)
    except MedicalRecordCryptoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt medical record",
        ) from exc

    write_audit_log(
        db,
        action="PATIENT_VIEW_OWN_RECORD",
        actor=current_user,
        target_type="medical_record",
        target_id=record.id,
        patient_id=patient.id,
        outcome="SUCCESS",
        detail="Patient viewed own medical record",
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
