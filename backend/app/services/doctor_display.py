from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.user import User


def is_placeholder_doctor_name(value: str | None) -> bool:
    normalized = str(value or "").strip().casefold().replace(" ", "")
    return normalized in {"", "norecord", "notrecorded", "unknown", "none", "null"}


def normalize_department(value: str | None) -> str:
    return str(value or "").strip().casefold()


def get_doctor_display_name(user: User, doctor: Doctor | None) -> str:
    if doctor is not None and doctor.name:
        display_name = doctor.name
    else:
        display_name = user.username
    return "" if is_placeholder_doctor_name(display_name) else display_name


def get_doctor_display_name_by_user_id(db: Session, user_id: int) -> str:
    result = (
        db.query(User, Doctor)
        .outerjoin(Doctor, Doctor.user_id == User.id)
        .filter(User.id == user_id)
        .first()
    )
    if result is None:
        return ""

    user, doctor = result
    return get_doctor_display_name(user, doctor)


def get_department_doctor_map(db: Session) -> dict[str, str]:
    rows = (
        db.query(User, Doctor)
        .join(Doctor, Doctor.user_id == User.id)
        .filter(User.role == "DOCTOR")
        .filter(User.status == "ACTIVE")
        .filter(Doctor.verified.is_(True))
        .order_by(Doctor.department.asc(), Doctor.name.asc())
        .all()
    )

    result: dict[str, str] = {}
    for user, doctor in rows:
        department_key = normalize_department(doctor.department)
        display_name = get_doctor_display_name(user, doctor)
        if department_key and display_name and department_key not in result:
            result[department_key] = display_name
    return result


def get_doctor_name_by_department(
    department_doctor_map: dict[str, str],
    department: str | None,
) -> str:
    departments = [
        normalize_department(item)
        for item in str(department or "").split(";")
        if normalize_department(item)
    ]

    for department_key in departments:
        doctor_name = department_doctor_map.get(department_key)
        if doctor_name:
            return doctor_name

    if not departments:
        return department_doctor_map.get(normalize_department("General Medicine"), "")

    return ""


def apply_doctor_name(
    item: dict,
    *,
    record_doctor_name: str | None,
    department_doctor_map: dict[str, str] | None = None,
    allow_department_fallback: bool = True,
    preserve_existing: bool = False,
) -> dict:
    item_copy = item.copy()
    doctor_name = record_doctor_name
    if preserve_existing:
        doctor_name = doctor_name or item_copy.get("doctor_name") or item_copy.get("doctor")

    if (
        allow_department_fallback
        and is_placeholder_doctor_name(str(doctor_name or ""))
        and department_doctor_map is not None
    ):
        doctor_name = get_doctor_name_by_department(
            department_doctor_map,
            str(item.get("department") or ""),
        )

    if doctor_name and not is_placeholder_doctor_name(str(doctor_name)):
        item_copy["doctor_name"] = doctor_name
        item_copy["doctor"] = doctor_name
    else:
        item_copy.pop("doctor_name", None)
        if is_placeholder_doctor_name(str(item_copy.get("doctor") or "")):
            item_copy.pop("doctor", None)
    return item_copy
