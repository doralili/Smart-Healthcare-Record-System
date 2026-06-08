import base64
import hashlib
import hmac
import json
import secrets
from copy import deepcopy
from typing import Any

from app.core.config import settings


WATERMARK_FIELD = "_security_watermark"
WATERMARK_VERSION = "demo-hmac-v1"
WATERMARK_ALGORITHM = "HMAC-SHA256"


def remove_security_watermark(record: dict[str, Any]) -> dict[str, Any]:
    clean_record = dict(record)
    clean_record.pop(WATERMARK_FIELD, None)
    return clean_record


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _watermark_key() -> bytes:
    decoded_key = base64.b64decode(settings.medical_record_key)
    return hmac.new(
        decoded_key,
        b"medical-record-watermark-demo-v1",
        hashlib.sha256,
    ).digest()


def _content_hash(record: dict[str, Any]) -> str:
    clean_record = remove_security_watermark(record)
    return hashlib.sha256(_canonical_json(clean_record).encode("utf-8")).hexdigest()


def _signature_payload(
    *,
    patient_id: int,
    doctor_id: int,
    issued_at: str,
    salt: str,
    record_hash: str,
) -> dict[str, Any]:
    return {
        "version": WATERMARK_VERSION,
        "algorithm": WATERMARK_ALGORITHM,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "issued_at": issued_at,
        "salt": salt,
        "record_hash": record_hash,
    }


def _sign_payload(payload: dict[str, Any]) -> str:
    signature = hmac.new(
        _watermark_key(),
        _canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def embed_record_watermark(
    record: dict[str, Any],
    *,
    patient_id: int,
    doctor_id: int,
    issued_at: str,
) -> dict[str, Any]:
    watermarked_record = deepcopy(remove_security_watermark(record))
    record_hash = _content_hash(watermarked_record)
    salt = secrets.token_urlsafe(16)
    payload = _signature_payload(
        patient_id=patient_id,
        doctor_id=doctor_id,
        issued_at=issued_at,
        salt=salt,
        record_hash=record_hash,
    )
    watermarked_record[WATERMARK_FIELD] = {
        **payload,
        "signature": _sign_payload(payload),
    }
    return watermarked_record


def verify_record_watermark(
    record: dict[str, Any],
    *,
    patient_id: int,
    doctor_id: int | None,
) -> dict[str, Any]:
    watermark = record.get(WATERMARK_FIELD)
    if not isinstance(watermark, dict):
        return {
            "status": "MISSING",
            "message": "No hidden signature watermark found",
            "issued_at": None,
            "signed_doctor_id": None,
            "record_hash": None,
        }

    required_values = {
        key: watermark.get(key)
        for key in ["version", "algorithm", "patient_id", "doctor_id", "issued_at", "salt", "record_hash", "signature"]
    }
    if any(value in {None, ""} for value in required_values.values()):
        return {
            "status": "INVALID",
            "message": "Watermark is incomplete",
            "issued_at": watermark.get("issued_at"),
            "signed_doctor_id": watermark.get("doctor_id"),
            "record_hash": watermark.get("record_hash"),
        }

    expected_payload = _signature_payload(
        patient_id=int(watermark["patient_id"]),
        doctor_id=int(watermark["doctor_id"]),
        issued_at=str(watermark["issued_at"]),
        salt=str(watermark["salt"]),
        record_hash=str(watermark["record_hash"]),
    )
    expected_signature = _sign_payload(expected_payload)
    actual_hash = _content_hash(record)

    if watermark.get("version") != WATERMARK_VERSION:
        message = "Unsupported watermark version"
    elif watermark.get("algorithm") != WATERMARK_ALGORITHM:
        message = "Unsupported watermark algorithm"
    elif int(watermark["patient_id"]) != patient_id:
        message = "Watermark patient does not match this record"
    elif doctor_id is not None and int(watermark["doctor_id"]) != doctor_id:
        message = "Watermark doctor does not match the last writer"
    elif not hmac.compare_digest(str(watermark["signature"]), expected_signature):
        message = "Watermark signature does not match"
    elif not hmac.compare_digest(str(watermark["record_hash"]), actual_hash):
        message = "Medical record content was changed after signing"
    else:
        return {
            "status": "VALID",
            "message": "Hidden signature watermark is valid",
            "issued_at": watermark.get("issued_at"),
            "signed_doctor_id": int(watermark["doctor_id"]),
            "record_hash": watermark.get("record_hash"),
        }

    return {
        "status": "INVALID",
        "message": message,
        "issued_at": watermark.get("issued_at"),
        "signed_doctor_id": watermark.get("doctor_id"),
        "record_hash": watermark.get("record_hash"),
    }
