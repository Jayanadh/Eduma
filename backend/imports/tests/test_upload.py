"""Upload and dry run of a students-v1 file (slice 4c S4C-05 to S4C-08)."""

import datetime as dt

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.permissions import today_for
from imports.contract import checksum, parse
from imports.models import ImportedRecord, ImportJob

from .helpers import HEADER, URL, csv_file, line, upload


def test_excel_style_file_parses(world, on, main, client_for):
    """Review Focus 2: BOM, CRLF line ends, blank trailing lines, padded values."""
    text = "\r\n".join(
        [HEADER, line(source="  S-1 ", name=" Kiran Rao "), line(source="S-2", name="Asha Devi"), ",,,", "", ""]
    )
    admin = client_for(world.a.slug, world.a_admin)
    made = upload(admin, SimpleUploadedFile("excel.csv", b"\xef\xbb\xbf" + text.encode(), "text/csv"))
    assert made.status_code == 201, made.json()
    assert made.json()["totals"] == {"rows": 2, "valid": 2, "error": 0, "duplicate": 0, "unchanged": 0, "changed": 0}
    rows = admin.get(f"{URL}/{made.json()['id']}/rows").json()["results"]
    assert [(row["row_number"], row["source_record_id"], row["full_name"]) for row in rows] == [
        (2, "S-1", "Kiran Rao"),
        (3, "S-2", "Asha Devi"),
    ]


def test_missing_columns_are_named(world, on, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    header = HEADER.replace("date_of_birth,", "").replace(",entry_date", "")
    refused = upload(admin, csv_file(header=header))
    assert refused.status_code == 422
    error = refused.json()["errors"][0]
    assert error["field"] == "file" and "date_of_birth" in error["message"] and "entry_date" in error["message"]
    assert not ImportJob.objects.exists()


def test_not_utf8_or_too_big(world, on, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    latin = SimpleUploadedFile("x.csv", HEADER.encode() + b"\nS-1,Ren\xe9", "text/csv")
    assert upload(admin, latin).json()["errors"][0]["field"] == "file"
    big = SimpleUploadedFile("big.csv", b"x" * (2 * 1024 * 1024 + 1), "text/csv")
    assert upload(admin, big).status_code == 422


def test_each_row_error_has_a_code(world, on, main, client_for):
    future = str(today_for(world.a) + dt.timedelta(days=1))
    rows = [
        line(source="S-1", name=""),
        line(source="S-2", born="2020-02-31"),
        line(source="S-3", born=future),
        line(source="S-4", campus_code="NOPE"),
        line(source="S-5", academic_year="2026-28"),
        line(source="S-6", entry_date="2024-01-01"),
        line(source="S-7", email="not-an-email"),
        line(source="S-8", born="unknown"),
    ]
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(*rows)).json()
    found = admin.get(f"{URL}/{job['id']}/rows", {"page_size": 20}).json()["results"]
    codes = {row["source_record_id"]: [(e["field"], e["code"]) for e in row["errors"]] for row in found}
    assert codes == {
        "S-1": [("full_name", "required")],
        "S-2": [("date_of_birth", "bad_date")],
        "S-3": [("date_of_birth", "future_date")],
        "S-4": [("campus_code", "unknown_campus")],
        "S-5": [("academic_year", "bad_year")],
        "S-6": [("entry_date", "entry_before_admission")],
        "S-7": [("email", "bad_email")],
        "S-8": [],
    }
    assert job["totals"]["error"] == 7 and job["totals"]["valid"] == 1


def test_duplicates_and_repeated_source_ids(world, on, enrolled, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    rows = [
        line(source="S-1", name="meera   RAO", born="2020-05-17"),  # the enrolled student, Meera Rao
        line(source="S-2", name="Twin One", born="2019-01-01"),
        line(source="S-3", name="twin one", born="2019-01-01"),
        line(source="S-2", name="Someone Else", born="2019-02-02"),
    ]
    job = upload(admin, csv_file(*rows)).json()
    found = {row["row_number"]: row for row in admin.get(f"{URL}/{job['id']}/rows").json()["results"]}
    assert found[2]["state"] == "duplicate"
    assert found[2]["duplicate_of"] == [
        {"kind": "student", "id": str(enrolled.id), "label": f"{enrolled.number} Meera Rao"}
    ]
    assert found[3]["state"] == "valid"
    assert found[4]["state"] == "duplicate" and found[4]["duplicate_of"][0] == {
        "kind": "row",
        "row_number": 3,
        "label": "Row 3 Twin One",
    }
    assert found[5]["state"] == "error" and found[5]["errors"][0]["code"] == "repeated_source_id"


def test_previously_imported_rows(world, on, main, enrolled, client_for):
    first, second = line(source="S-1"), line(source="S-2", name="Asha Devi")
    for source, text in (("S-1", first), ("S-2", line(source="S-2", name="Asha Devi Old"))):
        values = dict(zip(HEADER.split(","), text.split(","), strict=True))
        ImportedRecord.objects.create(
            institution=world.a, source_system="Old ERP", entity_type="student", source_record_id=source,
            checksum=checksum(values), job=_job(world), student=enrolled,
        )  # fmt: skip
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(first, second)).json()
    assert (job["totals"]["unchanged"], job["totals"]["changed"]) == (1, 1)
    other_system = upload(admin, csv_file(first, second), source_system="New ERP").json()
    assert other_system["totals"]["valid"] == 2


def _job(world):
    return ImportJob.objects.create(
        institution=world.a, source_system="Old ERP", original_name="old.csv", checksum="0" * 64, size=1
    )


def test_import_needs_its_permission_and_institution(world, on, registrar, client_for):
    assert upload(registrar, csv_file(line())).status_code == 403
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(line())).json()
    from admissions.tests.conftest import switch_on

    switch_on(world.b)
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(f"{URL}/{job['id']}").status_code == 404
    assert birch.get(f"{URL}/{job['id']}/rows").status_code == 404
    assert birch.get(URL).json()["count"] == 0


def test_file_is_stored_privately(world, on, client_for, settings):
    admin = client_for(world.a.slug, world.a_admin)
    job = ImportJob.objects.get(pk=upload(admin, csv_file(line())).json()["id"])
    assert job.file.path.startswith(str(settings.PRIVATE_MEDIA_ROOT / "imports" / str(world.a.id)))
    assert job.checksum and job.size > 0


def test_decide_only_possible_duplicates(world, on, enrolled, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(line(source="S-1", name="Meera Rao", born="2020-05-17"), line(source="S-2"))).json()
    rows = {row["row_number"]: row for row in admin.get(f"{URL}/{job['id']}/rows").json()["results"]}
    decided = admin.post(f"{URL}/{job['id']}/rows/{rows[2]['id']}/decide", {"decision": "create"}, format="json")
    assert decided.status_code == 200 and decided.json()["decision"] == "create"
    refused = admin.post(f"{URL}/{job['id']}/rows/{rows[3]['id']}/decide", {"decision": "skip"}, format="json")
    assert refused.status_code == 409
    assert (
        admin.post(f"{URL}/{job['id']}/rows/{rows[2]['id']}/decide", {"decision": "merge"}, format="json").status_code
        == 422
    )


def test_contract_parse_limits():
    import pytest
    from rest_framework.exceptions import ValidationError

    many = "\n".join([HEADER, *(line(source=f"S-{n}") for n in range(5001))]).encode()
    with pytest.raises(ValidationError):
        parse(many)
    with pytest.raises(ValidationError):
        parse(b"")


def test_empty_file_is_refused(world, on, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    assert upload(admin, SimpleUploadedFile("empty.csv", b"", "text/csv")).status_code == 422
