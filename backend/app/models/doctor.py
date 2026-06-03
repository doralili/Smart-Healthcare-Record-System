from sqlalchemy import Boolean, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.db.session import Base

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(100))
    license_no = Column(String(50))
    note = Column(Text)
    verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
