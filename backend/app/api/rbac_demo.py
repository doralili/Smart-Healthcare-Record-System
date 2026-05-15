from fastapi import APIRouter, Depends

from app.core.deps import require_roles
from app.models.user import User


router = APIRouter(prefix="/api/rbac", tags=["rbac-demo"])


@router.get("/patient")
def patient_only(current_user: User = Depends(require_roles("PATIENT"))):
    return {
        "message": "Patient access granted",
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/doctor")
def doctor_only(current_user: User = Depends(require_roles("DOCTOR"))):
    return {
        "message": "Doctor access granted",
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/admin")
def admin_only(current_user: User = Depends(require_roles("ADMIN"))):
    return {
        "message": "Admin access granted",
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/auditor")
def auditor_only(current_user: User = Depends(require_roles("AUDITOR"))):
    return {
        "message": "Auditor access granted",
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/admin-or-auditor")
def admin_or_auditor(
    current_user: User = Depends(require_roles("ADMIN", "AUDITOR")),
):
    return {
        "message": "Admin or auditor access granted",
        "username": current_user.username,
        "role": current_user.role,
    }
