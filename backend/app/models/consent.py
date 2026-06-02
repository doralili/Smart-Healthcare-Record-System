from sqlalchemy import Column, Integer, String, TIMESTAMP, Text
from sqlalchemy.sql import func
from app.db.session import Base

class Consent(Base):
    __tablename__ = "consents"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False)
    doctor_id = Column(Integer, nullable=False)
    record_scope = Column(String(20), nullable=False)
    permission = Column(String(50))
    status = Column(String(20), default="PENDING")
    request_reason = Column(Text)
    approve_note = Column(Text)
    consent_source = Column(String(30), nullable=False)
    default_scope = Column(String(20))
    start_time = Column(TIMESTAMP)
    end_time = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now())
    auto_granted_at = Column(TIMESTAMP)
    approved_at = Column(TIMESTAMP)
    revoked_at = Column(TIMESTAMP)
