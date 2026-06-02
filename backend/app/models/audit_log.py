from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, nullable=True)
    actor_role = Column(String(20), nullable=True)
    actor_username = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    doctor_id = Column(Integer, nullable=True)
    patient_id = Column(Integer, nullable=True)
    consent_id = Column(Integer, nullable=True)
    record_scope = Column(String(20), nullable=True)
    outcome = Column(String(20), nullable=False, default="SUCCESS")
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    previous_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=False)
