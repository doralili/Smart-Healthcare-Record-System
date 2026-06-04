import hashlib
import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.timezone import BEIJING_TZ, now_beijing
from app.models.audit_log import AuditLog
from app.models.user import User


def _hash_time(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=BEIJING_TZ)
    else:
        value = value.astimezone(BEIJING_TZ)
    return value.isoformat()


def _canonical_payload(log: AuditLog, previous_hash: str | None) -> str:
    payload: dict[str, Any] = {
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
        "created_at": _hash_time(log.created_at),
        "previous_hash": previous_hash,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def calculate_audit_hash(log: AuditLog, previous_hash: str | None = None) -> str:
    base = _canonical_payload(log, log.previous_hash if previous_hash is None else previous_hash)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def write_audit_log(
    db: Session,
    *,
    action: str,
    actor: User | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    consent_id: int | None = None,
    record_scope: str | None = None,
    outcome: str = "SUCCESS",
    detail: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    previous = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    previous_hash = previous.current_hash if previous else None
    created_at = now_beijing()

    log = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        actor_username=actor.username if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        consent_id=consent_id,
        record_scope=record_scope,
        outcome=outcome,
        detail=detail,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=created_at,
        previous_hash=previous_hash,
        current_hash="",
    )
    log.current_hash = calculate_audit_hash(log, previous_hash)
    db.add(log)
    return log


def request_audit_context(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def verify_audit_chain(db: Session) -> dict[str, Any]:
    logs = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    previous_hash: str | None = None

    for index, log in enumerate(logs):
        if log.previous_hash != previous_hash:
            return {
                "valid": False,
                "checked_count": index,
                "broken_log_id": log.id,
                "reason": "previous_hash mismatch",
                "expected_previous_hash": previous_hash,
                "actual_previous_hash": log.previous_hash,
            }

        expected_hash = calculate_audit_hash(log, previous_hash)
        if log.current_hash != expected_hash:
            return {
                "valid": False,
                "checked_count": index,
                "broken_log_id": log.id,
                "reason": "current_hash mismatch",
                "expected_current_hash": expected_hash,
                "actual_current_hash": log.current_hash,
            }

        previous_hash = log.current_hash

    return {
        "valid": True,
        "checked_count": len(logs),
        "broken_log_id": None,
        "reason": None,
    }
