from pydantic import BaseModel
from typing import Optional

class AccessRequestCreate(BaseModel):
    patient_id: int
    record_scope: str
    reason: Optional[str] = None