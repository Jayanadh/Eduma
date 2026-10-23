"""The `students-v1` import contract (slice 4c S4C-06): which columns a file has and what makes a row acceptable.
Pure functions: nothing here touches the database except the campus and duplicate lookups passed in."""

import csv
import datetime as dt
import hashlib
import io
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework.exceptions import ValidationError

COLUMNS = (
    "source_record_id",
    "full_name",
    "date_of_birth",
    "phone",
    "email",
    "address",
    "admitted_on",
    "academic_year",
    "place_code",
    "place_label",
    "campus_code",
    "entry_date",
    "guardian_name",
    "guardian_relationship",
    "guardian_phone",
    "guardian_email",
)
REQUIRED = frozenset(
    {"source_record_id", "full_name", "date_of_birth", "admitted_on", "academic_year", "place_code", "place_label",
     "entry_date"}
)  # fmt: skip
LIMITS = {
    "source_record_id": 100,
    "full_name": 150,
    "phone": 30,
    "address": 500,
    "place_code": 20,
    "place_label": 80,
    "guardian_name": 150,
    "guardian_relationship": 40,
    "guardian_phone": 30,
}
MAX_ROWS = 5000
YEAR = re.compile(r"^(\d{4})\s*[–-]\s*(\d{2})$")


def _refuse(message: str) -> ValidationError:
    return ValidationError({"file": [message]})


def parse(content: bytes) -> list[tuple[int, dict]]:
    """[(line number, {column: stripped value})] for every non-blank row."""
    try:
        text = content.decode("utf-8-sig")  # Excel's "CSV UTF-8" starts with a byte-order mark
    except UnicodeDecodeError as error:
        raise _refuse("Save the file as CSV UTF-8 and upload it again.") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise _refuse("The file is empty. Start from the template.")
    reader.fieldnames = [(name or "").strip().lower() for name in reader.fieldnames]
    if missing := sorted(REQUIRED - set(reader.fieldnames)):
        raise _refuse(f"These columns are missing: {', '.join(missing)}.")
    rows = []
    for raw in reader:
        values = {column: (raw.get(column) or "").strip() for column in COLUMNS}
        if any(values.values()):
            rows.append((reader.line_num, values))
        if len(rows) > MAX_ROWS:
            raise _refuse(f"Import at most {MAX_ROWS} rows at a time; split the file.")
    if not rows:
        raise _refuse("The file has no rows to import.")
    return rows


def checksum(values: dict) -> str:
    """Detects a changed row on a later import of the same source record."""
    return hashlib.sha256("\x1f".join(values.get(column, "") for column in COLUMNS).encode()).hexdigest()


def _date(value: str):
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def check(values: dict, campuses: dict, today: dt.date) -> tuple[dict, list[dict]]:
    """(cleaned values, errors). `campuses` maps lower-case campus code to campus id."""
    errors = []

    def error(field, code, message):
        if not any(e["field"] == field for e in errors):
            errors.append({"field": field, "code": code, "message": message})

    for column in sorted(REQUIRED, key=COLUMNS.index):
        if not values[column]:
            error(column, "required", f"Fill in {column}.")
    for column, limit in LIMITS.items():
        if len(values[column]) > limit:
            error(column, "too_long", f"Use at most {limit} characters.")
    clean = dict(values)
    born = values["date_of_birth"]
    if born.lower() == "unknown":
        clean["date_of_birth"] = None
    elif born:
        clean["date_of_birth"] = _date(born)
        if clean["date_of_birth"] is None:
            error("date_of_birth", "bad_date", "Write the date as YYYY-MM-DD, or 'unknown'.")
        elif clean["date_of_birth"] > today:
            error("date_of_birth", "future_date", "A date of birth can't be in the future.")
    for column in ("admitted_on", "entry_date"):
        if values[column]:
            clean[column] = _date(values[column])
            if clean[column] is None:
                error(column, "bad_date", "Write the date as YYYY-MM-DD.")
    if isinstance(clean["admitted_on"], dt.date) and isinstance(clean["entry_date"], dt.date):
        if clean["entry_date"] < clean["admitted_on"]:
            error("entry_date", "entry_before_admission", "The enrollment can't start before the admission.")
    if values["academic_year"]:
        found = YEAR.match(values["academic_year"])
        if not found or int(found[2]) != (int(found[1]) + 1) % 100:
            error("academic_year", "bad_year", "Write the academic year as 2026–27.")
        else:
            clean["academic_year"] = f"{found[1]}–{found[2]}"
            clean["entry_year"] = int(found[1])
    for column in ("email", "guardian_email"):
        if values[column]:
            try:
                validate_email(values[column])
            except DjangoValidationError:
                error(column, "bad_email", "This is not an email address.")
    if values["campus_code"]:
        clean["campus"] = campuses.get(values["campus_code"].lower())
        if clean["campus"] is None:
            error("campus_code", "unknown_campus", "No active campus here has this code.")
    else:
        clean["campus"] = None
    guardian = [values[c] for c in ("guardian_relationship", "guardian_phone", "guardian_email")]
    if any(guardian) and not values["guardian_name"]:
        error("guardian_name", "required", "Name the guardian, or leave all guardian columns empty.")
    return clean, errors


def same_person(name: str) -> str:
    return " ".join(name.split()).lower()
