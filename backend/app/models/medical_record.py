from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.session import Base


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    source = Column(String(30), nullable=False, default="SYNTHEA")
    record_type = Column(String(50), nullable=False, default="FHIR_SUMMARY")
    encrypted_data = Column(Text, nullable=False)
    nonce = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    updated_by_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
