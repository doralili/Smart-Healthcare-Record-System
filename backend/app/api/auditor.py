from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit_service import verify_audit_chain


router = APIRouter(prefix="/api/auditor", tags=["auditor"])


@router.get("/summary")
def get_audit_summary(
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    total = db.query(AuditLog).count()
    denied = db.query(AuditLog).filter(AuditLog.outcome == "DENIED").count()
    actions = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .all()
    )
    latest = db.query(AuditLog).order_by(AuditLog.id.desc()).first()

    return {
        "total_logs": total,
        "denied_logs": denied,
        "latest_log_at": latest.created_at if latest else None,
        "action_counts": [
            {"action": action, "count": count}
            for action, count in actions
        ],
    }


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 100,
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 500))
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(safe_limit).all()

    return {
        "logs": [
            {
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "actor_role": log.actor_role,
                "actor_username": log.actor_username,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "doctor_id": log.doctor_id,
                "patient_id": log.patient_id,
                "consent_id": log.consent_id,
                "record_scope": log.record_scope,
                "outcome": log.outcome,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at,
                "previous_hash": log.previous_hash,
                "current_hash": log.current_hash,
            }
            for log in logs
        ]
    }


@router.get("/verify-hash-chain")
def verify_hash_chain(
    current_user: User = Depends(require_roles("AUDITOR")),
    db: Session = Depends(get_db),
):
    return verify_audit_chain(db)
