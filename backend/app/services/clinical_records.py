from typing import Any


RecordDict = dict[str, Any]


def normalize_clinical_record_links(clinical_data: RecordDict) -> RecordDict:
    normalized = dict(clinical_data)
    encounters = [
        item
        for item in normalized.get("encounters", [])
        if isinstance(item, dict)
    ]

    if encounters:
        primary_encounter = encounters[0]
        primary_encounter.setdefault("id", "doctor-encounter-1")
        primary_encounter_id = primary_encounter.get("id")
    else:
        primary_encounter_id = None

    for key in ["conditions", "observations", "medications", "procedures"]:
        items = [
            item
            for item in normalized.get(key, [])
            if isinstance(item, dict)
        ]
        for item in items:
            if primary_encounter_id and not item.get("encounter_id"):
                item["encounter_id"] = primary_encounter_id
        normalized[key] = items

    normalized["encounters"] = encounters
    return normalized


def get_encounter_id(record: RecordDict) -> str | None:
    direct_value = record.get("encounter_id")
    if direct_value:
        return str(direct_value)

    encounter = record.get("encounter")
    if isinstance(encounter, dict):
        reference = encounter.get("reference")
        if reference:
            return str(reference).split("/")[-1] or None

    return None


def date_key(value: Any) -> str:
    if not value:
        return ""

    text = str(value)
    if len(text) >= 10:
        return text[:10]

    return text


def clinical_record_date(record: RecordDict) -> str:
    return date_key(
        record.get("recorded_date")
        or record.get("effective_datetime")
        or record.get("authored_on")
        or record.get("performed_datetime")
        or record.get("start")
    )


def is_related_to_diagnosis(record: RecordDict, diagnosis: RecordDict) -> bool:
    record_encounter_id = get_encounter_id(record)
    diagnosis_encounter_id = get_encounter_id(diagnosis)

    if record_encounter_id and diagnosis_encounter_id and record_encounter_id == diagnosis_encounter_id:
        return True

    record_date = clinical_record_date(record)
    diagnosis_date = clinical_record_date(diagnosis)
    return bool(record_date and diagnosis_date and record_date == diagnosis_date)


def filter_related_clinical_records(clinical_data: RecordDict) -> RecordDict:
    conditions = [
        item
        for item in clinical_data.get("conditions", [])
        if isinstance(item, dict)
    ]

    if not conditions:
        filtered = dict(clinical_data)
        filtered["conditions"] = []
        filtered["observations"] = [
            item for item in clinical_data.get("observations", []) if isinstance(item, dict)
        ]
        filtered["medications"] = [
            item for item in clinical_data.get("medications", []) if isinstance(item, dict)
        ]
        filtered["procedures"] = [
            item for item in clinical_data.get("procedures", []) if isinstance(item, dict)
        ]
        return filtered

    def only_related(items: Any) -> list[RecordDict]:
        if not isinstance(items, list):
            return []

        return [
            item
            for item in items
            if isinstance(item, dict)
            and any(is_related_to_diagnosis(item, condition) for condition in conditions)
        ]

    filtered = dict(clinical_data)
    filtered["conditions"] = conditions
    filtered["observations"] = only_related(clinical_data.get("observations", []))
    filtered["medications"] = only_related(clinical_data.get("medications", []))
    filtered["procedures"] = only_related(clinical_data.get("procedures", []))
    return filtered
