from pydantic import BaseModel
from typing import Literal, Optional

class AccessRequestCreate(BaseModel):
    patient_id: int
    record_scope: Literal["DEFAULT", "EXTRA"]
    reason: Optional[str] = None
