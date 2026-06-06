import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
FHIR_DIR = PROJECT_ROOT / "synthea" / "output" / "fhir"

sys.path.append(str(BACKEND_DIR))

from app.core.timezone import now_beijing
from app.db.session import SessionLocal
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.user import User
from app.services.crypto_service import encrypt_record_json


RESOURCE_TYPES = {
    "Patient",
    "Encounter",
    "Condition",
    "Observation",
    "MedicationRequest",
    "Procedure",
}

DEMO_PATIENT_USERNAMES = [f"patient{index}" for index in range(1, 11)]

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
        "myocardial",
        "pneumonia",
        "prediabetes",
        "pulmonary",
        "renal",
        "respiratory",
        "sepsis",
        "stroke",
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


def load_fhir_bundle(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def collect_resources(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    resources = {resource_type: [] for resource_type in RESOURCE_TYPES}

    for entry in bundle.get("entry", []):
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue

        resource_type = resource.get("resourceType")
        if resource_type in resources:
            resources[resource_type].append(resource)

    return resources


def get_display_text(value: Any) -> str | None:
    if isinstance(value, dict):
        if value.get("text"):
            return value["text"]

        coding = value.get("coding")
        if isinstance(coding, list) and coding:
            first = coding[0]
            if isinstance(first, dict):
                return first.get("display") or first.get("code")

    return None


def get_reference_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    reference = value.get("reference")
    if not reference:
        return None

    return str(reference).split("/")[-1]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None

    return date.fromisoformat(value[:10])


def parse_patient(patient: dict[str, Any]) -> dict[str, Any]:
    names = patient.get("name") or []
    first_name = ""
    last_name = ""

    if names:
        name = names[0]
        given = name.get("given") or []
        family = name.get("family") or ""

        first_name = " ".join(str(part) for part in given)
        last_name = str(family)

    telecom = patient.get("telecom") or []
    phone = None
    for item in telecom:
        if item.get("system") == "phone":
            phone = item.get("value")
            break

    addresses = patient.get("address") or []
    address_text = None
    if addresses:
        address = addresses[0]
        line = address.get("line") or []
        parts = [
            " ".join(str(part) for part in line),
            address.get("city"),
            address.get("state"),
            address.get("postalCode"),
            address.get("country"),
        ]
        address_text = ", ".join(str(part) for part in parts if part)

    deceased_datetime = patient.get("deceasedDateTime")
    deceased_boolean = patient.get("deceasedBoolean")
    deceased = bool(deceased_datetime or deceased_boolean)

    return {
        "synthea_patient_id": patient.get("id"),
        "full_name": " ".join(part for part in [first_name, last_name] if part),
        "gender": patient.get("gender"),
        "birth_date": parse_date(patient.get("birthDate")),
        "phone": phone,
        "address": address_text,
        "deceased": deceased,
        "deceased_datetime": deceased_datetime,
    }


def parse_encounter(resource: dict[str, Any]) -> dict[str, Any]:
    encounter_type = None
    types = resource.get("type") or []
    if types:
        encounter_type = get_display_text(types[0])

    encounter_class = resource.get("class") or {}

    return {
        "id": resource.get("id"),
        "status": resource.get("status"),
        "class": encounter_class.get("code"),
        "type": encounter_type,
        "start": (resource.get("period") or {}).get("start"),
        "end": (resource.get("period") or {}).get("end"),
    }


def classify_department_for_text(*values: Any) -> str | None:
    text = " ".join(str(value) for value in values if value).lower()
    text = re.sub(
        r"\s*\((finding|disorder|procedure|observable entity|regime/therapy)\)\s*",
        " ",
        text,
    )
    if not text:
        return "General Medicine"

    scores = {
        department: sum(1 for keyword in keywords if keyword in text)
        for department, keywords in DEPARTMENT_KEYWORDS.items()
    }
    best_department, best_score = max(scores.items(), key=lambda item: item[1])

    if best_score == 0:
        return "General Medicine"

    return best_department


def parse_condition(resource: dict[str, Any]) -> dict[str, Any]:
    code = get_display_text(resource.get("code"))
    return {
        "id": resource.get("id"),
        "encounter_id": get_reference_id(resource.get("encounter")),
        "clinical_status": get_display_text(resource.get("clinicalStatus")),
        "code": code,
        "department": classify_department_for_text(code),
        "recorded_date": resource.get("recordedDate"),
    }


def parse_observation(resource: dict[str, Any]) -> dict[str, Any]:
    value = None

    if "valueQuantity" in resource:
        quantity = resource["valueQuantity"]
        number = quantity.get("value")
        unit = quantity.get("unit") or quantity.get("code")
        value = f"{number} {unit}".strip()
    elif "valueCodeableConcept" in resource:
        value = get_display_text(resource["valueCodeableConcept"])
    elif "valueString" in resource:
        value = resource.get("valueString")
    elif "valueBoolean" in resource:
        value = resource.get("valueBoolean")
    elif "component" in resource:
        parts = []
        for component in resource.get("component", []):
            label = get_display_text(component.get("code"))
            quantity = component.get("valueQuantity") or {}
            number = quantity.get("value")
            unit = quantity.get("unit") or quantity.get("code")
            if label and number is not None:
                parts.append(f"{label}: {number} {unit}".strip())
        value = "; ".join(parts) if parts else None

    code = get_display_text(resource.get("code"))
    return {
        "id": resource.get("id"),
        "encounter_id": get_reference_id(resource.get("encounter")),
        "status": resource.get("status"),
        "code": code,
        "value": value,
        "department": classify_department_for_text(code, value),
        "effective_datetime": resource.get("effectiveDateTime"),
    }


def parse_medication_request(resource: dict[str, Any]) -> dict[str, Any]:
    medication = resource.get("medicationCodeableConcept")

    medication_text = get_display_text(medication)
    return {
        "id": resource.get("id"),
        "encounter_id": get_reference_id(resource.get("encounter")),
        "status": resource.get("status"),
        "intent": resource.get("intent"),
        "medication": medication_text,
        "department": classify_department_for_text(medication_text),
        "authored_on": resource.get("authoredOn"),
    }


def parse_procedure(resource: dict[str, Any]) -> dict[str, Any]:
    performed = resource.get("performedDateTime")
    if performed is None:
        performed = (resource.get("performedPeriod") or {}).get("start")

    code = get_display_text(resource.get("code"))
    return {
        "id": resource.get("id"),
        "encounter_id": get_reference_id(resource.get("encounter")),
        "status": resource.get("status"),
        "code": code,
        "department": classify_department_for_text(code),
        "performed_datetime": performed,
    }


def build_record(resources: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "encounters": [
            parse_encounter(resource)
            for resource in resources["Encounter"]
        ],
        "conditions": [
            parse_condition(resource)
            for resource in resources["Condition"]
        ],
        "observations": [
            parse_observation(resource)
            for resource in resources["Observation"]
        ],
        "medications": [
            parse_medication_request(resource)
            for resource in resources["MedicationRequest"]
        ],
        "procedures": [
            parse_procedure(resource)
            for resource in resources["Procedure"]
        ],
    }


def get_available_patient_demo_users(db) -> list[User]:
    users = (
        db.query(User)
        .filter(User.username.in_(DEMO_PATIENT_USERNAMES))
        .filter(User.role == "PATIENT")
        .all()
    )
    user_ids = [user.id for user in users]
    bound_user_ids = {
        patient.user_id
        for patient in (
            db.query(Patient)
            .filter(Patient.user_id.in_(user_ids))
            .all()
        )
        if patient.user_id is not None
    }
    users_by_name = {user.username: user for user in users}

    return [
        users_by_name[username]
        for username in DEMO_PATIENT_USERNAMES
        if username in users_by_name and users_by_name[username].id not in bound_user_ids
    ]


def import_patient_bundle(
    db,
    patient_data: dict[str, Any],
    record_data: dict[str, Any],
    bind_user_id: int | None,
) -> tuple[str, bool]:
    existing_patient = (
        db.query(Patient)
        .filter(Patient.synthea_patient_id == patient_data["synthea_patient_id"])
        .first()
    )

    if existing_patient is not None:
        existing_record = (
            db.query(MedicalRecord)
            .filter(MedicalRecord.patient_id == existing_patient.id)
            .first()
        )

        if existing_patient.user_id is None and bind_user_id is not None:
            existing_patient.user_id = bind_user_id
            print(f"Bound existing patient: {patient_data['full_name']}")

            if existing_record is None:
                encrypted_data, nonce = encrypt_record_json(record_data)
                db.add(
                    MedicalRecord(
                        patient_id=existing_patient.id,
                        source="SYNTHEA",
                        record_type="FHIR_SUMMARY",
                        encrypted_data=encrypted_data,
                        nonce=nonce,
                        created_at=now_beijing(),
                    )
                )
                print(f"Added missing record for existing patient: {patient_data['full_name']}")

            return "bound_existing", True

        if existing_record is None:
            encrypted_data, nonce = encrypt_record_json(record_data)
            db.add(
                MedicalRecord(
                    patient_id=existing_patient.id,
                    source="SYNTHEA",
                    record_type="FHIR_SUMMARY",
                    encrypted_data=encrypted_data,
                    nonce=nonce,
                    created_at=now_beijing(),
                )
            )
            print(f"Added missing record for existing patient: {patient_data['full_name']}")
            return "record_added_existing", False

        encrypted_data, nonce = encrypt_record_json(record_data)
        existing_record.encrypted_data = encrypted_data
        existing_record.nonce = nonce

        print(f"Updated existing record: {patient_data['full_name']}")
        return "record_updated_existing", False

    encrypted_data, nonce = encrypt_record_json(record_data)
    now = now_beijing()

    patient = Patient(
        user_id=bind_user_id,
        synthea_patient_id=patient_data["synthea_patient_id"],
        full_name=patient_data["full_name"],
        gender=patient_data["gender"],
        birth_date=patient_data["birth_date"],
        phone=patient_data["phone"],
        address=patient_data["address"],
        created_at=now,
    )

    db.add(patient)
    db.flush()

    medical_record = MedicalRecord(
        patient_id=patient.id,
        source="SYNTHEA",
        record_type="FHIR_SUMMARY",
        encrypted_data=encrypted_data,
        nonce=nonce,
        created_at=now,
    )

    db.add(medical_record)

    print(
        f"Imported patient: {patient.full_name} "
        f"(conditions={len(record_data['conditions'])}, "
        f"observations={len(record_data['observations'])}, "
        f"medications={len(record_data['medications'])}, "
        f"procedures={len(record_data['procedures'])})"
    )

    return "imported", bind_user_id is not None


def main():
    if not FHIR_DIR.exists():
        print("Synthea FHIR output directory does not exist.")
        return

    files = sorted(FHIR_DIR.glob("*.json"))

    if not files:
        print("No FHIR JSON files found.")
        return

    db = SessionLocal()

    try:
        patient_demo_users = get_available_patient_demo_users(db)
        next_demo_user_index = 0
        imported_count = 0
        bound_existing_count = 0
        record_added_existing_count = 0
        record_updated_existing_count = 0
        skipped_existing_count = 0
        skipped_deceased_count = 0

        for path in files:
            bundle = load_fhir_bundle(path)
            resources = collect_resources(bundle)

            if not resources["Patient"]:
                continue

            patient_data = parse_patient(resources["Patient"][0])

            if patient_data["deceased"]:
                skipped_deceased_count += 1
                print(
                    f"Skip deceased patient: {patient_data['full_name']} "
                    f"({patient_data['deceased_datetime']})"
                )
                continue

            record_data = build_record(resources)

            candidate_bind_user_id = None
            if next_demo_user_index < len(patient_demo_users):
                candidate_bind_user_id = patient_demo_users[next_demo_user_index].id

            status, used_demo_user = import_patient_bundle(
                db=db,
                patient_data=patient_data,
                record_data=record_data,
                bind_user_id=candidate_bind_user_id,
            )

            if used_demo_user:
                next_demo_user_index += 1

            if status == "imported":
                imported_count += 1
            elif status == "bound_existing":
                bound_existing_count += 1
            elif status == "record_added_existing":
                record_added_existing_count += 1
            elif status == "record_updated_existing":
                record_updated_existing_count += 1
            elif status == "skipped_existing":
                skipped_existing_count += 1

        db.commit()

        print("\nImport finished.")
        print(f"Imported living patients: {imported_count}")
        print(f"Bound existing patients: {bound_existing_count}")
        print(f"Added missing records for existing patients: {record_added_existing_count}")
        print(f"Updated existing records: {record_updated_existing_count}")
        print(f"Skipped existing patients: {skipped_existing_count}")
        print(f"Skipped deceased patients: {skipped_deceased_count}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
