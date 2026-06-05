from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text

from app.db.session import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    synthea_patient_id = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
