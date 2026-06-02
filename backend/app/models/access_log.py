from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from app.db.session import Base

class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, nullable=False)
    patient_id = Column(Integer, nullable=False)
    consent_id = Column(Integer, nullable=True)
    action = Column(String(20), nullable=False)  # ACCESS / DENIED
    record_scope = Column(String(20), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
