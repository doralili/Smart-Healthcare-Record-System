from sqlalchemy import Column, DateTime, Integer, String, Text
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
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    auto_granted_at = Column(DateTime(timezone=True))
    approved_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
