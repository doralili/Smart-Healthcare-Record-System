from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_password
from app.core.timezone import now_beijing
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.consent import Consent
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.user import User
from app.services.audit_service import verify_audit_chain, write_audit_log


router = APIRouter(prefix="/api/admin", tags=["admin"])
CONSENT_VALID_DAYS = 14

ManagedRole = Literal["DOCTOR", "AUDITOR", "ADMIN"]
AccountStatus = Literal["ACTIVE", "DISABLED", "PENDING"]


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)
    role: ManagedRole
    department: str | None = None
    license_no: str | None = None
    note: str | None = None


class UpdateUserStatusRequest(BaseModel):
    status: AccountStatus


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=72)


class UpdateDoctorRequest(BaseModel):
    department: str | None = None
    license_no: str | None = None
    note: str | None = None
    verified: bool | None = None
    account_status: AccountStatus | None = None


class AssignDoctorRequest(BaseModel):
    doctor_user_id: int
    patient_id: int
    note: str | None = None


def _doctor_status(user: User, doctor: Doctor | None) -> str:
    if user.status == "DISABLED":
        return "DISABLED"
    if doctor and doctor.verified:
        return "APPROVED"
    return "PENDING"


def _get_doctor_profile(db: Session, user_id: int) -> Doctor | None:
    return db.query(Doctor).filter(Doctor.user_id == user_id).first()


@router.get("/overview")
def get_admin_overview(
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    recent_since = now_beijing() - timedelta(hours=24)
    hash_status = verify_audit_chain(db)

    return {
        "user_count": db.query(User).count(),
        "doctor_count": db.query(User).filter(User.role == "DOCTOR").count(),
        "patient_count": db.query(User).filter(User.role == "PATIENT").count(),
        "disabled_user_count": db.query(User).filter(User.status == "DISABLED").count(),
        "medical_record_count": db.query(MedicalRecord).count(),
        "consent_count": db.query(Consent).count(),
        "recent_audit_log_count": db.query(AuditLog)
        .filter(AuditLog.created_at >= recent_since)
        .count(),
        "hash_chain_valid": hash_status["valid"],
        "hash_chain_checked_count": hash_status["checked_count"],
        "record_access_note": "Admin can view record counts only. Decrypted medical content is restricted.",
    }


@router.get("/users")
def list_users(
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.id.asc()).all()
    doctor_profiles = {
        doctor.user_id: doctor
        for doctor in db.query(Doctor).all()
    }

    return {
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "created_at": user.created_at,
                "last_login_at": user.last_login_at,
                "doctor_status": _doctor_status(user, doctor_profiles.get(user.id))
                if user.role == "DOCTOR"
                else None,
            }
            for user in users
        ]
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_managed_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        status="ACTIVE",
        created_at=now_beijing(),
    )
    db.add(user)
    db.flush()

    if payload.role == "DOCTOR":
        db.add(
            Doctor(
                user_id=user.id,
                name=username,
                department=payload.department,
                license_no=payload.license_no,
                note=payload.note,
                verified=False,
            )
        )

    write_audit_log(
        db,
        action="ADMIN_CREATE_USER",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        outcome="SUCCESS",
        detail=f"Created {payload.role} account",
    )
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
    }


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and payload.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Admin cannot disable own account")

    user.status = payload.status
    write_audit_log(
        db,
        action="ADMIN_UPDATE_USER_STATUS",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        outcome="SUCCESS",
        detail=f"Set status to {payload.status}",
    )
    db.commit()

    return {"id": user.id, "status": user.status}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.password)
    write_audit_log(
        db,
        action="ADMIN_RESET_PASSWORD",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        outcome="SUCCESS",
        detail="Password reset by admin",
    )
    db.commit()

    return {"id": user.id, "message": "Password reset"}


@router.get("/doctors")
def list_doctors(
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    doctor_users = db.query(User).filter(User.role == "DOCTOR").order_by(User.id.asc()).all()
    doctor_profiles = {
        doctor.user_id: doctor
        for doctor in db.query(Doctor).all()
    }

    return {
        "doctors": [
            {
                "user_id": user.id,
                "username": user.username,
                "account_status": user.status,
                "doctor_status": _doctor_status(user, doctor_profiles.get(user.id)),
                "department": doctor_profiles.get(user.id).department
                if doctor_profiles.get(user.id)
                else None,
                "license_no": doctor_profiles.get(user.id).license_no
                if doctor_profiles.get(user.id)
                else None,
                "note": doctor_profiles.get(user.id).note
                if doctor_profiles.get(user.id)
                else None,
                "verified": bool(doctor_profiles.get(user.id).verified)
                if doctor_profiles.get(user.id)
                else False,
                "created_at": user.created_at,
            }
            for user in doctor_users
        ]
    }


@router.patch("/doctors/{user_id}")
def update_doctor(
    user_id: int,
    payload: UpdateDoctorRequest,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None or user.role != "DOCTOR":
        raise HTTPException(status_code=404, detail="Doctor user not found")

    doctor = _get_doctor_profile(db, user_id)
    if doctor is None:
        doctor = Doctor(user_id=user.id, name=user.username, verified=False)
        db.add(doctor)

    if payload.department is not None:
        doctor.department = payload.department
    if payload.license_no is not None:
        doctor.license_no = payload.license_no
    if payload.note is not None:
        doctor.note = payload.note
    if payload.verified is not None:
        doctor.verified = payload.verified
    if payload.account_status is not None:
        user.status = payload.account_status

    write_audit_log(
        db,
        action="ADMIN_UPDATE_DOCTOR",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        doctor_id=user.id,
        outcome="SUCCESS",
        detail="Doctor profile or review status updated",
    )
    db.commit()

    return {
        "user_id": user.id,
        "doctor_status": _doctor_status(user, doctor),
        "account_status": user.status,
        "verified": doctor.verified,
    }


@router.get("/patients")
def list_patients_for_assignment(
    q: str = "",
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    query = db.query(Patient).order_by(Patient.id.asc())
    if q.strip():
        query = query.filter(Patient.full_name.ilike(f"%{q.strip()}%"))

    patients = query.limit(100).all()
    return {
        "patients": [
            {
                "id": patient.id,
                "full_name": patient.full_name,
                "gender": patient.gender,
                "birth_date": patient.birth_date,
                "user_id": patient.user_id,
            }
            for patient in patients
        ]
    }


@router.post("/assignments")
def assign_patient_to_doctor(
    payload: AssignDoctorRequest,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    doctor_user = db.get(User, payload.doctor_user_id)
    if doctor_user is None or doctor_user.role != "DOCTOR":
        raise HTTPException(status_code=404, detail="Doctor user not found")
    if doctor_user.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Doctor account is not active")

    doctor_profile = _get_doctor_profile(db, doctor_user.id)
    if doctor_profile is None or not doctor_profile.verified:
        raise HTTPException(status_code=400, detail="Doctor is not approved")

    patient = db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    consent = db.query(Consent).filter(
        Consent.doctor_id == doctor_user.id,
        Consent.patient_id == patient.id,
    ).first()

    now = now_beijing()
    expires_at = now + timedelta(days=CONSENT_VALID_DAYS)
    if consent is None:
        consent = Consent(
            doctor_id=doctor_user.id,
            patient_id=patient.id,
            record_scope="DEFAULT",
            permission="READ",
            status="ACTIVE",
            consent_source="DEFAULT_CLINICAL",
            default_scope="DEFAULT_CLINICAL",
            start_time=now,
            end_time=expires_at,
            auto_granted_at=now,
        )
        db.add(consent)
        db.flush()
    else:
        consent.record_scope = "DEFAULT"
        consent.permission = "READ"
        consent.status = "ACTIVE"
        consent.consent_source = "DEFAULT_CLINICAL"
        consent.default_scope = "DEFAULT_CLINICAL"
        consent.start_time = consent.start_time or now
        consent.end_time = expires_at
        consent.revoked_at = None
        consent.auto_granted_at = consent.auto_granted_at or now

    write_audit_log(
        db,
        action="ADMIN_ASSIGN_DEFAULT_CLINICAL",
        actor=current_user,
        target_type="patient",
        target_id=patient.id,
        doctor_id=doctor_user.id,
        patient_id=patient.id,
        consent_id=consent.id,
        record_scope="DEFAULT",
        outcome="SUCCESS",
        detail=payload.note or "Admin assigned default clinical access",
    )
    db.commit()

    return {
        "consent_id": consent.id,
        "doctor_user_id": doctor_user.id,
        "patient_id": patient.id,
        "status": consent.status,
        "record_scope": consent.record_scope,
        "consent_source": consent.consent_source,
    }
