from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.user import User
from app.services.crypto_service import MedicalRecordCryptoError, decrypt_record_json


router = APIRouter(prefix="/api/patient/me/records", tags=["patient-records"])


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
