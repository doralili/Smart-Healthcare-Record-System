from app.core.timezone import BEIJING_TZ, now_beijing
from app.models.consent import Consent


def consent_display_status(consent: Consent) -> str:
    end_time = consent.end_time
    if end_time is not None and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=BEIJING_TZ)
    elif end_time is not None:
        end_time = end_time.astimezone(BEIJING_TZ)

    if (
        consent.status == "ACTIVE"
        and end_time is not None
        and end_time <= now_beijing()
    ):
        return "EXPIRED"
    return consent.status


def consent_priority(consent: Consent) -> tuple[int, int]:
    status_rank = {
        "ACTIVE": 4,
        "PENDING": 3,
        "REJECTED": 2,
        "REVOKED": 1,
        "EXPIRED": 0,
    }.get(consent_display_status(consent), 0)
    scope_rank = {"EXTRA": 2, "DEFAULT": 1}.get(consent.record_scope, 0)
    return status_rank, scope_rank


def best_consents_by_doctor(consents: list[Consent]) -> dict[int, Consent]:
    result: dict[int, Consent] = {}
    for consent in consents:
        current_best = result.get(consent.doctor_id)
        if current_best is None or consent_priority(consent) > consent_priority(current_best):
            result[consent.doctor_id] = consent
    return result
