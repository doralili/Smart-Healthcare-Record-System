from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.user import User
from app.services.audit_service import verify_audit_chain
from app.services.crypto_service import MedicalRecordCryptoError, decrypt_record_json
from app.services.record_watermark import verify_record_watermark


router = APIRouter(prefix="/api/auditor", tags=["auditor"])


@router.get("/summary")
def get_audit_summary(
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    total = db.query(AuditLog).count()
    denied = db.query(AuditLog).filter(AuditLog.outcome == "DENIED").count()
    actions = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .all()
    )
    latest = db.query(AuditLog).order_by(AuditLog.id.desc()).first()

    return {
        "total_logs": total,
        "denied_logs": denied,
        "latest_log_at": latest.created_at if latest else None,
        "action_counts": [
            {"action": action, "count": count}
            for action, count in actions
        ],
    }


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 100,
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 500))
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(safe_limit).all()
    patient_ids = {log.patient_id for log in logs if log.patient_id is not None}
    doctor_user_ids = {log.doctor_id for log in logs if log.doctor_id is not None}

    patient_names = {
        patient.id: patient.full_name
        for patient in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}
    doctor_usernames = {
        user.id: user.username
        for user in db.query(User).filter(User.id.in_(doctor_user_ids)).all()
    } if doctor_user_ids else {}
    doctor_names = {
        doctor.user_id: doctor.name
        for doctor in db.query(Doctor).filter(Doctor.user_id.in_(doctor_user_ids)).all()
    } if doctor_user_ids else {}

    return {
        "logs": [
            {
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "actor_role": log.actor_role,
                "actor_username": log.actor_username,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "doctor_id": log.doctor_id,
                "doctor_username": doctor_usernames.get(log.doctor_id),
                "doctor_name": doctor_names.get(log.doctor_id),
                "patient_id": log.patient_id,
                "patient_name": patient_names.get(log.patient_id),
                "consent_id": log.consent_id,
                "record_scope": log.record_scope,
                "outcome": log.outcome,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at,
                "previous_hash": log.previous_hash,
                "current_hash": log.current_hash,
            }
            for log in logs
        ]
    }


@router.get("/verify-hash-chain")
def verify_hash_chain(
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    return verify_audit_chain(db)


@router.get("/record-watermarks")
def list_record_watermarks(
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    records = db.query(MedicalRecord).order_by(MedicalRecord.created_at.desc()).all()
    patient_ids = {record.patient_id for record in records if record.patient_id is not None}
    doctor_user_ids = {
        record.updated_by_doctor_id
        for record in records
        if record.updated_by_doctor_id is not None
    }

    patient_names = {
        patient.id: patient.full_name
        for patient in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}
    doctor_usernames = {
        user.id: user.username
        for user in db.query(User).filter(User.id.in_(doctor_user_ids)).all()
    } if doctor_user_ids else {}
    doctor_names = {
        doctor.user_id: doctor.name
        for doctor in db.query(Doctor).filter(Doctor.user_id.in_(doctor_user_ids)).all()
    } if doctor_user_ids else {}

    def ensure_doctor_loaded(user_id: int | None) -> None:
        if user_id is None or user_id in doctor_usernames:
            return

        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            doctor_usernames[user_id] = user.username

        doctor = db.query(Doctor).filter(Doctor.user_id == user_id).first()
        if doctor is not None:
            doctor_names[user_id] = doctor.name

    status_counts = {
        "VALID": 0,
        "INVALID": 0,
        "MISSING": 0,
        "DECRYPTION_FAILED": 0,
    }
    items = []

    for record in records:
        try:
            decrypted_record = decrypt_record_json(record.encrypted_data, record.nonce)
            verification = verify_record_watermark(
                decrypted_record,
                patient_id=record.patient_id,
                doctor_id=record.updated_by_doctor_id,
            )
        except MedicalRecordCryptoError:
            verification = {
                "status": "DECRYPTION_FAILED",
                "message": "Unable to decrypt medical record for watermark verification",
                "issued_at": None,
                "signed_doctor_id": None,
                "record_hash": None,
            }

        status = verification["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        signed_doctor_id = verification.get("signed_doctor_id")
        if signed_doctor_id is not None:
            try:
                signed_doctor_id = int(signed_doctor_id)
            except (TypeError, ValueError):
                signed_doctor_id = None
        updated_by_doctor_id = record.updated_by_doctor_id
        display_doctor_id = signed_doctor_id or updated_by_doctor_id
        ensure_doctor_loaded(signed_doctor_id)
        ensure_doctor_loaded(updated_by_doctor_id)

        items.append(
            {
                "record_id": record.id,
                "patient_id": record.patient_id,
                "patient_name": patient_names.get(record.patient_id),
                "doctor_id": display_doctor_id,
                "doctor_username": doctor_usernames.get(display_doctor_id),
                "doctor_name": doctor_names.get(display_doctor_id),
                "signed_doctor_id": signed_doctor_id,
                "signed_doctor_username": doctor_usernames.get(signed_doctor_id),
                "signed_doctor_name": doctor_names.get(signed_doctor_id),
                "updated_by_doctor_id": updated_by_doctor_id,
                "updated_by_doctor_username": doctor_usernames.get(updated_by_doctor_id),
                "updated_by_doctor_name": doctor_names.get(updated_by_doctor_id),
                "source": record.source,
                "record_type": record.record_type,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "watermark_status": status,
                "watermark_message": verification["message"],
                "watermark_issued_at": verification["issued_at"],
                "watermark_record_hash": verification["record_hash"],
            }
        )

    return {
        "summary": {
            "total_records": len(records),
            "valid": status_counts["VALID"],
            "invalid": status_counts["INVALID"],
            "missing": status_counts["MISSING"],
            "decryption_failed": status_counts["DECRYPTION_FAILED"],
        },
        "records": items,
    }
