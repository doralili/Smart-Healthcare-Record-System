from datetime import datetime, timedelta
from typing import Any

from app.core.timezone import now_beijing
from app.services.doctor_display import apply_doctor_name


def dedupe_by_id(items: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for item in items:
        item_id = item.get(key)
        if item_id and item_id not in seen:
            seen.add(item_id)
            unique.append(item)
        elif not item_id:
            unique.append(item)
    return unique


def mask_address(address: str | None) -> str:
    if not address:
        return ""
    return str(address).split(",")[0].strip()


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    phone_str = str(phone)
    if len(phone_str) >= 7:
        return phone_str[:3] + "****" + phone_str[-4:]
    return phone_str


def filter_records_by_date(records: list[dict[str, Any]], days: int = 365) -> list[dict[str, Any]]:
    if not records:
        return []

    one_year_ago = now_beijing() - timedelta(days=days)
    filtered = []
    for record in records:
        date_str = (
            record.get("recorded_date")
            or record.get("effective_datetime")
            or record.get("authored_on")
            or record.get("performed_datetime")
        )
        if date_str:
            try:
                if isinstance(date_str, str):
                    record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    record_date = date_str
                if record_date >= one_year_ago:
                    filtered.append(record)
            except Exception:
                filtered.append(record)
        else:
            filtered.append(record)
    return filtered


def build_diagnosis_list(
    conditions: list[dict[str, Any]],
    encounters_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []

    def encounter_payload(enc: dict[str, Any], cond: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": enc.get("id"),
            "type": enc.get("type", ""),
            "class": enc.get("class", ""),
            "status": enc.get("status", ""),
            "start": enc.get("start", ""),
            "doctor_name": enc.get("doctor_name") or cond.get("doctor_name", ""),
            "doctor": enc.get("doctor") or cond.get("doctor", ""),
            "doctor_department": enc.get("doctor_department", ""),
        }

    for condition in conditions:
        encounter_id = condition.get("encounter_id")
        related_encounters = [
            encounter_payload(encounter, condition)
            for encounter in condition.get("related_encounters", [])
            if isinstance(encounter, dict)
        ]

        if not related_encounters and encounter_id and encounter_id in encounters_map:
            related_encounters = [encounter_payload(encounters_map[encounter_id], condition)]

        result.append(
            {
                "name": condition.get("code", ""),
                "department": condition.get("department", "Not Classified"),
                "status": condition.get("clinical_status", "active"),
                "date": condition.get("recorded_date", "")[:10]
                if condition.get("recorded_date")
                else "",
                "encounter_id": encounter_id,
                "doctor_name": condition.get("doctor_name", ""),
                "doctor": condition.get("doctor", ""),
                "related_encounters": related_encounters,
                "related_observations": condition.get("related_observations", []),
                "related_medications": condition.get("related_medications", []),
                "related_procedures": condition.get("related_procedures", []),
            }
        )
    return result


def collect_related_items(
    conditions: list[dict[str, Any]],
    related_key: str,
) -> list[dict[str, Any]]:
    related_items = []
    seen = set()
    for condition in conditions:
        for item in condition.get(related_key, []):
            if not isinstance(item, dict):
                continue
            item_key = str(item.get("id") or id(item))
            if item_key in seen:
                continue
            seen.add(item_key)
            related_items.append(item)
    return related_items


def build_medications_list(medications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": medication.get("medication", ""),
            "start_date": medication.get("authored_on", "")[:10]
            if medication.get("authored_on")
            else "",
            "stop_date": medication.get("stop_date", "")[:10]
            if medication.get("stop_date")
            else "",
        }
        for medication in medications
        if medication.get("medication")
    ]


def build_observations_list(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "test_name": observation.get("code", ""),
            "value": observation.get("value", ""),
            "date": observation.get("effective_datetime", "")[:10]
            if observation.get("effective_datetime")
            else "",
        }
        for observation in observations
        if observation.get("code")
    ]


def build_procedures_list(procedures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": procedure.get("code", ""),
            "date": procedure.get("performed_datetime", "")[:10]
            if procedure.get("performed_datetime")
            else "",
        }
        for procedure in procedures
        if procedure.get("code")
    ]


def enrich_clinical_data_doctor_names(
    clinical_data: dict[str, Any],
    *,
    record_doctor_name: str | None,
    department_doctor_map: dict[str, str],
) -> dict[str, Any]:
    enriched = dict(clinical_data)

    for key in ["conditions", "medications", "observations", "procedures", "encounters"]:
        enriched[key] = [
            apply_doctor_name(
                item,
                record_doctor_name=record_doctor_name,
                department_doctor_map=department_doctor_map,
                allow_department_fallback=(key == "conditions"),
                preserve_existing=True,
            )
            for item in enriched.get(key, [])
            if isinstance(item, dict)
        ]

    for condition in enriched.get("conditions", []):
        if not isinstance(condition, dict):
            continue
        condition_doctor_name = condition.get("doctor_name") or condition.get("doctor")
        for related_key in [
            "related_encounters",
            "related_medications",
            "related_observations",
            "related_procedures",
        ]:
            condition[related_key] = [
                apply_doctor_name(
                    item,
                    record_doctor_name=str(condition_doctor_name or record_doctor_name or ""),
                    department_doctor_map=department_doctor_map,
                    allow_department_fallback=False,
                    preserve_existing=True,
                )
                for item in condition.get(related_key, [])
                if isinstance(item, dict)
            ]

    return enriched


def add_doctor_identity_to_record(
    record_data: dict[str, Any],
    *,
    doctor_name: str,
    doctor_department: str,
) -> dict[str, Any]:
    for key in ["encounters", "conditions", "observations", "medications", "procedures"]:
        for item in record_data.get(key, []):
            if "doctor_name" not in item or not item["doctor_name"]:
                item["doctor_name"] = doctor_name
            if "doctor_department" not in item or not item["doctor_department"]:
                item["doctor_department"] = doctor_department
    return record_data
