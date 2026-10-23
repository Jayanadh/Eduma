"""Staged student imports (slice 4c §2, §4): upload and dry run, duplicate decisions, commit, discard and undo."""

import hashlib

from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.permissions import today_for
from common import audit
from common.exceptions import Problem
from imports import contract
from imports.models import ImportedRecord, ImportJob, ImportRow
from students.models import Student

MAX_BYTES = 2 * 1024 * 1024
ENTITY = "student"
STATES = [state for state, _ in ImportRow.State.choices]


def _provenance(institution, source_system: str, source_id: str):
    return ImportedRecord.objects.filter(
        institution=institution, source_system=source_system, entity_type=ENTITY, source_record_id=source_id
    ).first()


def _rows(institution, source_system: str, parsed: list) -> list[ImportRow]:
    """Each parsed row with its state: error, already imported (unchanged or changed), possible duplicate, or ready."""
    campuses = {code.lower(): pk for pk, code in institution.campuses.filter(is_active=True).values_list("id", "code")}
    today = today_for(institution)
    seen_ids: set[str] = set()
    seen_people: dict[tuple, tuple[int, str]] = {}
    rows = []
    for number, values in parsed:
        clean, errors = contract.check(values, campuses, today)
        source_id = values["source_record_id"]
        if source_id and source_id in seen_ids:
            errors.append(
                {"field": "source_record_id", "code": "repeated_source_id", "message": "This id is on an earlier row."}
            )
        seen_ids.add(source_id)
        row = ImportRow(row_number=number, source_record_id=source_id, raw=values, errors=errors)
        row.checksum = contract.checksum(values)
        earlier = _provenance(institution, source_system, source_id) if source_id else None
        if errors:
            row.state = ImportRow.State.ERROR
        elif earlier is not None:
            row.state = ImportRow.State.UNCHANGED if earlier.checksum == row.checksum else ImportRow.State.CHANGED
        else:
            row.state = ImportRow.State.VALID
            born = clean["date_of_birth"]
            if born is not None:
                key = (contract.same_person(values["full_name"]), born)
                matches = [
                    {"kind": "student", "id": str(s.id), "label": f"{s.number} {s.person.full_name}"}
                    for s in Student.objects.possible_duplicates(institution, values["full_name"], born)
                ]
                if key in seen_people:
                    earlier_row, earlier_name = seen_people[key]
                    matches.append(
                        {"kind": "row", "row_number": earlier_row, "label": f"Row {earlier_row} {earlier_name}"}
                    )
                if matches:
                    row.state, row.duplicate_of = ImportRow.State.DUPLICATE, matches
                seen_people.setdefault(key, (number, values["full_name"]))
        rows.append(row)
    return rows


def totals(rows) -> dict:
    counted = {"rows": len(rows), **{state: 0 for state in STATES}}
    for row in rows:
        counted[row.state] += 1
    return counted


def upload(actor, institution, file, source_system: str) -> ImportJob:
    if file.size > MAX_BYTES:
        raise ValidationError({"file": ["Upload a file of at most 2 MB; split larger ones."]})
    content = file.read()
    rows = _rows(institution, source_system, contract.parse(content))
    with transaction.atomic():
        job = ImportJob(
            institution=institution,
            source_system=source_system,
            original_name=file.name[:200],
            checksum=hashlib.sha256(content).hexdigest(),
            size=len(content),
            totals=totals(rows),
            created_by=actor,
        )
        job.file.save("upload.csv", ContentFile(content), save=False)
        job.save()
        for row in rows:
            row.job = job
        ImportRow.objects.bulk_create(rows)
        audit.log(
            actor,
            "import.uploaded",
            job,
            f"Checked {job.original_name}: {job.totals['valid']} ready, {job.totals['error']} with errors",
            institution=institution,
            changes={"source_system": source_system, **job.totals},
        )
    return job


def decide(actor, row: ImportRow, decision: str) -> ImportRow:
    with transaction.atomic():
        row = ImportRow.objects.select_for_update().select_related("job").get(pk=row.pk)
        if row.job.status != ImportJob.Status.VALIDATED or row.state != ImportRow.State.DUPLICATE:
            raise Problem(
                409, "invalid_transition", "Only a possible duplicate in an unimported file needs a decision."
            )
        row.decision = decision
        row.save(update_fields=["decision"])
        return row
