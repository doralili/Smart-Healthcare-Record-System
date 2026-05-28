from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from app.core.db import Base

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(100))
    license_no = Column(String(50))
    verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())