"""Staged student imports (slice 4c §2, §4): upload and dry run, duplicate decisions, commit, discard and undo."""

import csv
import hashlib
import io

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.permissions import today_for
from common import audit
from common.exceptions import Problem
from imports import contract
from imports.models import ImportedRecord, ImportJob, ImportRow
from institutions.models import Institution
from students import guardians
from students.models import Enrollment, GuardianLink, Person, Student

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
        row = ImportRow(row_number=number, source_record_id=source_id[:100], raw=values, errors=errors)
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


def canonical_source(institution, source_system: str) -> str:
    """The spelling already used here for this source, so "old  erp" finds what "Old ERP" imported."""
    wanted = " ".join(source_system.split())
    used = ImportJob.objects.filter(institution=institution).values_list("source_system", flat=True).distinct()
    return next((name for name in used if name.casefold() == wanted.casefold()), wanted)


def upload(actor, institution, file, source_system: str) -> ImportJob:
    source_system = canonical_source(institution, source_system)
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


def _job(actor_version: int, job: ImportJob) -> ImportJob:
    job = ImportJob.objects.select_for_update().get(pk=job.pk)
    job.check_version(actor_version)
    return job


def _not_validated(job: ImportJob) -> Problem:
    return Problem(409, "invalid_transition", f"This file is {job.get_status_display().lower()}.")


def _create(actor, institution, job: ImportJob, row: ImportRow, clean: dict, number: str) -> Student:
    values = row.raw
    person = Person.objects.create(
        institution=institution,
        full_name=values["full_name"],
        date_of_birth=clean["date_of_birth"],
        phone=values["phone"],
        email=values["email"],
        address=values["address"],
    )
    student = Student.objects.create(
        institution=institution,
        person=person,
        number=number,
        admitted_on=clean["admitted_on"],
    )
    Enrollment.objects.create(
        student=student,
        institution=institution,
        academic_year=clean["academic_year"],
        place_code=values["place_code"],
        place_label=values["place_label"],
        campus_id=clean["campus"],
        entry_date=clean["entry_date"],
    )
    ImportedRecord.objects.create(
        institution=institution,
        source_system=job.source_system,
        entity_type=ENTITY,
        source_record_id=row.source_record_id,
        checksum=row.checksum,
        job=job,
        student=student,
    )
    audit.log(
        actor,
        "student.imported",
        student,
        f"{student.number} imported from {job.source_system} ({job.original_name}, row {row.row_number})",
        institution=institution,
        changes={"batch": str(job.id), "source_record_id": row.source_record_id},
    )
    if values["guardian_name"]:
        adult = {
            "full_name": values["guardian_name"],
            "phone": values["guardian_phone"],
            "email": values["guardian_email"],
        }
        relationship = values["guardian_relationship"] or "Guardian"
        guardians.propose(actor, student, adult, relationship, source=GuardianLink.Source.IMPORT)
    return student


def commit(actor, job: ImportJob, version: int) -> ImportJob:
    """All or nothing. Rows already imported meanwhile (by another batch) are counted, not created again."""
    institution = job.institution
    with transaction.atomic():
        job = _job(version, job)
        if job.status != ImportJob.Status.VALIDATED:
            raise _not_validated(job)
        if job.rows.filter(state=ImportRow.State.DUPLICATE, decision="").exists():
            raise Problem(409, "undecided_duplicates", "Decide every possible duplicate before importing.")
        Institution.objects.select_for_update().get(pk=institution.pk)  # student numbers are handed out one at a time
        campuses = {c.lower(): pk for pk, c in institution.campuses.filter(is_active=True).values_list("id", "code")}
        today = today_for(institution)
        counts = {"created": 0, "skipped": 0, "unchanged": 0, "changed": 0, "error": 0}
        next_numbers: dict[int, int] = {}  # entry year -> next sequence, read once under the institution lock
        for row in job.rows.all():
            if row.state in (ImportRow.State.ERROR, ImportRow.State.UNCHANGED, ImportRow.State.CHANGED):
                counts[row.state] += 1
                continue
            if row.state == ImportRow.State.DUPLICATE and row.decision == ImportRow.Decision.SKIP:
                counts["skipped"] += 1
                continue
            earlier = _provenance(institution, job.source_system, row.source_record_id)
            clean, errors = contract.check(row.raw, campuses, today)
            if earlier is not None or errors:
                if earlier is not None:
                    same = earlier.checksum == row.checksum
                    row.state = ImportRow.State.UNCHANGED if same else ImportRow.State.CHANGED
                else:
                    row.state, row.errors = ImportRow.State.ERROR, errors  # e.g. a campus closed since the dry run
                row.save(update_fields=["state", "errors"])
                counts[row.state] += 1
                continue
            year = clean["entry_year"]
            if year not in next_numbers:
                next_numbers[year] = int(Student.objects.next_number(institution, year).split("-")[1])
            row.student = _create(actor, institution, job, row, clean, f"{year}-{next_numbers[year]:04d}")
            next_numbers[year] += 1
            row.save(update_fields=["student"])
            counts["created"] += 1
        job.status, job.committed_by, job.committed_at = ImportJob.Status.COMMITTED, actor, timezone.now()
        job.totals = {**job.totals, **counts}
        job.save()
        audit.log(
            actor,
            "import.committed",
            job,
            f"Imported {counts['created']} students from {job.original_name}",
            institution=institution,
            changes=counts,
        )
        return job


def discard(actor, job: ImportJob, version: int) -> ImportJob:
    with transaction.atomic():
        job = _job(version, job)
        if job.status != ImportJob.Status.VALIDATED:
            raise _not_validated(job)
        job.file.delete(save=False)
        job.status = ImportJob.Status.DISCARDED
        job.save()
        audit.log(actor, "import.discarded", job, f"Discarded {job.original_name}", institution=job.institution)
        return job


def undo_blocker(job: ImportJob, students=None) -> str | None:
    """Why the batch can no longer be undone, or None: anything it created has been touched since. A few queries
    over the whole batch, whatever its size."""
    students = students if students is not None else Student.objects.filter(provenance__job=job)
    if found := students.filter(user__isnull=False).first():
        return f"{found.number} has a login."
    if found := students.filter(enrollments__periods__isnull=False).first():
        return f"{found.number} has been placed in a class."
    if found := students.annotate(episodes=Count("enrollments")).filter(episodes__gt=1).first():
        return f"{found.number} has another enrollment."
    academic = (
        Q(enrollments__registrations__isnull=False)
        | Q(enrollments__attempts__isnull=False)
        | Q(enrollments__transfers__isnull=False)
        | Q(enrollments__attendance__isnull=False)
        | Q(enrollments__submissions__isnull=False)
        | Q(enrollments__candidacies__isnull=False)
        | Q(enrollments__promotions__isnull=False)
        | Q(documents__isnull=False)
        | Q(fee_accounts__isnull=False)
        | Q(holds__isnull=False)
        | Q(overrides__isnull=False)
    )
    if found := students.filter(academic).first():
        return f"{found.number} has registrations, attendance, a hold or an academic record."
    links = GuardianLink.objects.filter(student__in=students)
    if found := links.exclude(source=GuardianLink.Source.IMPORT, status=GuardianLink.Status.PROPOSED).first():
        return f"{found.student.number} has a guardian added or checked since the import."
    if found := students.exclude(version=1).first():
        return f"{found.number} has changed since it was imported."
    return None


def undo(actor, job: ImportJob, version: int) -> ImportJob:
    with transaction.atomic():
        job = _job(version, job)
        if job.status != ImportJob.Status.COMMITTED:
            raise Problem(409, "invalid_transition", "Only an imported file can be undone.")
        ids = list(Student.objects.select_for_update().filter(provenance__job=job).values_list("id", flat=True))
        students = Student.objects.filter(pk__in=ids)
        if reason := undo_blocker(job, students):
            raise Problem(409, "undo_blocked", f"This import can't be undone: {reason} Correct the records instead.")
        links = GuardianLink.objects.filter(student_id__in=ids)
        adults = list(links.values_list("adult_id", flat=True))
        people = list(students.values_list("person_id", flat=True))
        links.delete()
        Enrollment.objects.filter(student_id__in=ids).delete()
        ImportedRecord.objects.filter(job=job).delete()
        students.delete()
        Person.objects.filter(pk__in=[*adults, *people]).delete()
        job.status, job.undone_by, job.undone_at = ImportJob.Status.UNDONE, actor, timezone.now()
        job.save()
        audit.log(
            actor,
            "import.undone",
            job,
            f"Undid the import of {job.original_name}: {len(ids)} students removed",
            institution=job.institution,
            changes={"removed": len(ids)},
        )
        return job


def _safe(cell: str) -> str:
    """Spreadsheets run cells that start like a formula; a leading apostrophe makes them text."""
    return f"'{cell}" if cell[:1] in ("=", "+", "-", "@", "\t", "\r") else cell


def error_csv(job: ImportJob) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["row", "column", "code", "message", "source_record_id"])
    for row in job.rows.filter(state=ImportRow.State.ERROR):
        for error in row.errors:
            writer.writerow(
                [
                    _safe(str(x))
                    for x in (row.row_number, error["field"], error["code"], error["message"], row.source_record_id)
                ]
            )
    return out.getvalue()


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(contract.COLUMNS)
    writer.writerow(
        ["OLD-1001", "Kiran Rao", "2019-04-02", "", "", "7 Lake Road", "2024-06-01", "2026–27", "C2", "Class 2", "MAIN",
         "2026-06-01", "Lata Rao", "Mother", "+91 90000 33333", ""]
    )  # fmt: skip
    return out.getvalue()
