from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.auditor import router as auditor_router
from app.api.rbac_demo import router as rbac_demo_router
from app.api.patient_records import router as patient_records_router
from app.api.doctor import router as doctor_router
from app.db.init_db import ensure_audit_schema

app = FastAPI(title="Smart Healthcare Record Security System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup():
    ensure_audit_schema()


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(rbac_demo_router)
app.include_router(patient_records_router)
app.include_router(doctor_router)
app.include_router(auditor_router)
