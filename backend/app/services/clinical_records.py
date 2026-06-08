import re
from typing import Any


RecordDict = dict[str, Any]

DEPARTMENT_KEYWORDS = {
    "Internal Medicine": [
        "a1c",
        "anemia",
        "asthma",
        "atrial",
        "blood pressure",
        "bronchitis",
        "cardiac",
        "cardio",
        "chronic",
        "copd",
        "coronary",
        "diabetes",
        "diabetic",
        "digestive",
        "disorder",
        "dyspnea",
        "emphysema",
        "endocrine",
        "fever",
        "glucose",
        "hba1c",
        "heart",
        "hemoglobin a1c",
        "hyperglycemia",
        "hypertension",
        "hypoglycemia",
        "infection",
        "influenza",
        "insulin",
        "kidney",
        "liver",
        "metformin",
        "metoprolol",
        "myocardial",
        "nitroglycerin",
        "pneumonia",
        "prediabetes",
        "pulmonary",
        "renal",
        "respiratory",
        "sepsis",
        "simvastatin",
        "stroke",
        "clopidogrel",
    ],
    "Surgery": [
        "amputation",
        "appendectomy",
        "arthroscopy",
        "biopsy",
        "burn",
        "contusion",
        "dislocation",
        "fracture",
        "injury",
        "laceration",
        "operation",
        "operative",
        "orthopedic",
        "procedure",
        "repair",
        "replacement",
        "sprain",
        "surgery",
        "surgical",
        "trauma",
        "wound",
    ],
    "Obstetrics and Gynecology": [
        "abortion",
        "antenatal",
        "birth",
        "contraceptive",
        "delivery",
        "female infertility",
        "gynecologic",
        "labor",
        "maternal",
        "obstetric",
        "postnatal",
        "postpartum",
        "pregnancy",
        "prenatal",
        "uterine",
        "vaginal",
    ],
    "Pediatrics": [
        "birth weight",
        "child",
        "childhood",
        "infant",
        "newborn",
        "pediatric",
        "well child",
    ],
    "Dentistry": [
        "caries",
        "dental",
        "dentist",
        "filling",
        "fractured dental",
        "gingival",
        "gingivitis",
        "oral",
        "teeth",
        "tooth",
    ],
    "Mental Health": [
        "abuse",
        "anxiety",
        "depression",
        "mental",
        "panic",
        "post traumatic",
        "ptsd",
        "social isolation",
        "stress",
        "substance",
    ],
    "Rehabilitation and Preventive Care": [
        "body mass index",
        "bmi",
        "diet",
        "education",
        "employment",
        "exercise",
        "housing",
        "lifestyle",
        "medication review",
        "obesity",
        "preventive",
        "screening",
        "social contact",
        "transportation",
    ],
}


def normalize_clinical_record_links(clinical_data: RecordDict) -> RecordDict:
    normalized = dict(clinical_data)
    normalized.pop("_security_watermark", None)
    encounters = [
        item
        for item in normalized.get("encounters", [])
        if isinstance(item, dict)
    ]

    for encounter in encounters:
        encounter["class"] = normalize_encounter_class(encounter.get("class"))

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
    strip_non_diagnosis_departments(normalized)
    return normalized


def normalize_encounter_class(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    key = text.casefold().replace("-", "").replace("_", "").replace(" ", "")
    class_map = {
        "amb": "AMB",
        "ambulatory": "AMB",
        "outpatient": "AMB",
        "emergency": "EMER",
        "emer": "EMER",
        "er": "EMER",
        "inpatient": "IMP",
        "inpatientencounter": "IMP",
        "imp": "IMP",
        "home": "HH",
        "hh": "HH",
        "virtual": "VR",
        "vr": "VR",
    }
    return class_map.get(key, text.upper() if len(text) <= 6 else text)


def strip_non_diagnosis_departments(clinical_data: RecordDict) -> RecordDict:
    for key in ["encounters", "observations", "medications", "procedures"]:
        for item in clinical_data.get(key, []):
            if isinstance(item, dict):
                item.pop("department", None)
    return clinical_data


def normalize_encounter_id(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("urn:uuid:"):
        return text.removeprefix("urn:uuid:")
    return text


def get_encounter_id(record: RecordDict) -> str | None:
    direct_value = record.get("encounter_id")
    if direct_value:
        return normalize_encounter_id(direct_value)

    encounter = record.get("encounter")
    if isinstance(encounter, dict):
        reference = encounter.get("reference")
        if reference:
            return normalize_encounter_id(str(reference).split("/")[-1]) or None

    return None


def get_visit_id(record: RecordDict) -> str | None:
    encounter_id = get_encounter_id(record)
    if encounter_id:
        return encounter_id

    if record.get("id") and any(key in record for key in ["start", "end", "type", "class"]):
        return normalize_encounter_id(record.get("id"))

    return None


def minute_key(value: Any) -> str:
    if not value:
        return ""

    text = str(value)
    if len(text) >= 16 and text[10] in {"T", " "}:
        return text[:16]

    if len(text) >= 10:
        return text[:10]

    return text


def clinical_record_time(record: RecordDict) -> str:
    return minute_key(
        record.get("recorded_date")
        or record.get("effective_datetime")
        or record.get("authored_on")
        or record.get("performed_datetime")
        or record.get("start")
    )


def visit_group_key(record: RecordDict) -> str:
    encounter_id = get_visit_id(record)
    if encounter_id:
        return f"encounter:{encounter_id}"

    record_time = clinical_record_time(record)
    if record_time:
        return f"time:{record_time}"

    return ""


def diagnosis_department(record: RecordDict) -> str:
    return str(record.get("department") or "").strip().casefold()


def classify_department_for_text(*values: Any) -> str:
    text = " ".join(str(value) for value in values if value).lower()
    text = re.sub(
        r"\s*\((finding|disorder|procedure|observable entity|regime/therapy)\)\s*",
        " ",
        text,
    )
    if not text:
        return ""

    scores = {
        department.casefold(): sum(1 for keyword in keywords if keyword in text)
        for department, keywords in DEPARTMENT_KEYWORDS.items()
    }
    best_department, best_score = max(scores.items(), key=lambda item: item[1])
    return best_department if best_score > 0 else ""


def classify_department_for_medication(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(
        r"\b(oral|tablet|tab|capsule|cap|mg|mcg|ml|hr|extended release|solution|spray|injection)\b",
        " ",
        text,
    )
    return classify_department_for_text(text)


def clinical_record_department(record: RecordDict) -> str:
    if record.get("medication"):
        return classify_department_for_medication(record.get("medication"))

    return classify_department_for_text(
        record.get("code"),
        record.get("value"),
        record.get("test_name"),
        record.get("name"),
        record.get("type"),
    )


def is_observation(record: RecordDict) -> bool:
    return bool(record.get("effective_datetime") and record.get("code"))


def is_routine_or_social_observation(record: RecordDict) -> bool:
    if not is_observation(record):
        return False

    text = " ".join(
        str(value or "")
        for value in [
            record.get("code"),
            record.get("value"),
            record.get("test_name"),
            record.get("name"),
        ]
    ).casefold()

    excluded_terms = [
        "asset",
        "assets",
        "income",
        "prapare",
        "risk and experience",
        "social determinants",
        "social risk",
    ]
    return any(term in text for term in excluded_terms)


def is_keyword_match_for_department(record: RecordDict, diagnosis: RecordDict) -> bool:
    department = diagnosis_department(diagnosis)
    if not department:
        return False
    record_department = clinical_record_department(record)
    return not record_department or record_department == department


def is_related_to_diagnosis(record: RecordDict, diagnosis: RecordDict) -> bool:
    record_time = clinical_record_time(record)
    diagnosis_time = clinical_record_time(diagnosis)
    return bool(record_time and diagnosis_time and record_time == diagnosis_time)


def is_in_same_visit(record: RecordDict, diagnosis: RecordDict) -> bool:
    record_group = visit_group_key(record)
    diagnosis_group = visit_group_key(diagnosis)
    return bool(record_group and diagnosis_group and record_group == diagnosis_group)


def related_records_for_diagnosis(
    items: Any,
    diagnosis: RecordDict,
    *,
    require_same_minute: bool,
) -> list[RecordDict]:
    if not isinstance(items, list):
        return []

    related = []
    for item in items:
        if not isinstance(item, dict) or not is_in_same_visit(item, diagnosis):
            continue

        if is_routine_or_social_observation(item):
            continue

        if not is_keyword_match_for_department(item, diagnosis):
            continue

        if not require_same_minute:
            related.append(item)
            continue

        item_department = clinical_record_department(item)
        if is_related_to_diagnosis(item, diagnosis) or item_department == diagnosis_department(diagnosis):
            related.append(item)

    return related


def related_records_for_visit(items: Any, diagnosis: RecordDict) -> list[RecordDict]:
    if not isinstance(items, list):
        return []

    return [
        item
        for item in items
        if isinstance(item, dict)
        and is_in_same_visit(item, diagnosis)
    ]


def attach_related_records_to_diagnoses(clinical_data: RecordDict) -> RecordDict:
    conditions = [
        item
        for item in clinical_data.get("conditions", [])
        if isinstance(item, dict)
    ]
    encounters = [
        item
        for item in clinical_data.get("encounters", [])
        if isinstance(item, dict)
    ]
    observations = [
        item
        for item in clinical_data.get("observations", [])
        if isinstance(item, dict)
    ]
    medications = [
        item
        for item in clinical_data.get("medications", [])
        if isinstance(item, dict)
    ]
    procedures = [
        item
        for item in clinical_data.get("procedures", [])
        if isinstance(item, dict)
    ]

    conditions_by_visit: dict[str, list[RecordDict]] = {}
    for condition in conditions:
        key = visit_group_key(condition)
        if not key:
            continue
        conditions_by_visit.setdefault(key, []).append(condition)

    enriched_conditions = []
    for condition in conditions:
        condition_copy = dict(condition)
        same_visit_conditions = conditions_by_visit.get(visit_group_key(condition), [condition])
        same_visit_departments = {
            diagnosis_department(item)
            for item in same_visit_conditions
            if diagnosis_department(item)
        }

        require_same_minute = len(same_visit_departments) > 1
        related_encounters = related_records_for_visit(encounters, condition)
        related_observations = related_records_for_diagnosis(
            observations,
            condition,
            require_same_minute=require_same_minute,
        )
        related_medications = related_records_for_diagnosis(
            medications,
            condition,
            require_same_minute=require_same_minute,
        )
        related_procedures = related_records_for_diagnosis(
            procedures,
            condition,
            require_same_minute=require_same_minute,
        )

        condition_copy["related_encounters"] = related_encounters
        condition_copy["related_observations"] = related_observations
        condition_copy["related_medications"] = related_medications
        condition_copy["related_procedures"] = related_procedures
        enriched_conditions.append(condition_copy)

    enriched = dict(clinical_data)
    enriched["conditions"] = enriched_conditions
    return enriched


def filter_related_clinical_records(clinical_data: RecordDict) -> RecordDict:
    conditions = [
        item
        for item in clinical_data.get("conditions", [])
        if isinstance(item, dict)
    ]

    if not conditions:
        filtered = dict(clinical_data)
        filtered["conditions"] = []
        filtered["observations"] = []
        filtered["medications"] = []
        filtered["procedures"] = []
        return filtered

    enriched = attach_related_records_to_diagnoses(dict(clinical_data, conditions=conditions))
    enriched_conditions = [
        item
        for item in enriched.get("conditions", [])
        if isinstance(item, dict)
    ]

    def only_related(key: str) -> list[RecordDict]:
        related_items: list[RecordDict] = []
        seen: set[str] = set()
        related_key = f"related_{key}"

        for condition in enriched_conditions:
            for item in condition.get(related_key, []):
                if not isinstance(item, dict):
                    continue

                item_key = str(item.get("id") or id(item))
                if item_key in seen:
                    continue
                seen.add(item_key)
                related_items.append(item)

        return related_items

    filtered = dict(clinical_data)
    filtered["conditions"] = enriched_conditions
    filtered["observations"] = only_related("observations")
    filtered["medications"] = only_related("medications")
    filtered["procedures"] = only_related("procedures")
    return filtered
