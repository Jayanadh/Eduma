"""Commit, provenance, undo and the error file (slice 4c S4C-07 to S4C-11, TST-025)."""

import threading

import pytest
from django.db import connection

from accounts.models import Membership
from imports import services
from imports.models import ImportedRecord, ImportJob
from students.models import GuardianLink, Person, Student

from .helpers import HEADER, URL, csv_file, line, upload

FILE = [
    line(source="S-1", name="Kiran Rao", guardian_name="", guardian_relationship="", guardian_phone=""),
    line(source="S-2", name="Meera Rao", born="2020-05-17"),  # the enrolled student
    line(source="S-3", name="Bad Date", born="2019-13-01"),
    line(source="S-4", name="Asha Devi", born="2018-08-08"),
    line(source="S-5", name="meera rao", born="2020-05-17", place_code="C3", place_label="Class 3"),
]


def rows_of(client, job):
    return {row["source_record_id"]: row for row in client.get(f"{URL}/{job['id']}/rows").json()["results"]}


def decide(client, job, row, decision):
    return client.post(f"{URL}/{job['id']}/rows/{row['id']}/decide", {"decision": decision}, format="json")


def commit(client, job):
    current = client.get(f"{URL}/{job['id']}").json()
    return client.post(f"{URL}/{job['id']}/commit", {"version": current["version"]}, format="json")


@pytest.fixture
def admin(world, on, main, enrolled, client_for):
    return client_for(world.a.slug, world.a_admin)


def test_tst025_preview_decide_commit_and_rerun(world, admin, enrolled):
    job = upload(admin, csv_file(*FILE)).json()
    assert job["totals"] == {"rows": 5, "valid": 2, "error": 1, "duplicate": 2, "unchanged": 0, "changed": 0}
    refused = commit(admin, job)
    assert refused.status_code == 409 and refused.json()["code"] == "undecided_duplicates"
    rows = rows_of(admin, job)
    decide(admin, job, rows["S-2"], "skip")
    decide(admin, job, rows["S-5"], "create")
    done = commit(admin, job)
    assert done.status_code == 200, done.json()
    totals = done.json()["totals"]
    assert (totals["created"], totals["skipped"], totals["error"]) == (3, 1, 1)
    assert Student.objects.count() == 4
    numbers = sorted(Student.objects.exclude(pk=enrolled.pk).values_list("number", flat=True))
    assert numbers == ["2026-0001", "2026-0002", "2026-0003"]
    kiran = ImportedRecord.objects.get(source_record_id="S-1").student
    assert kiran.enrollments.get().place_label == "Class 2" and kiran.admitted_on.isoformat() == "2024-06-01"
    assert commit(admin, job).status_code == 409
    again = upload(admin, csv_file(*FILE)).json()
    assert (again["totals"]["unchanged"], again["totals"]["duplicate"], again["totals"]["error"]) == (3, 1, 1)
    decide(admin, again, rows_of(admin, again)["S-2"], "skip")
    assert commit(admin, again).json()["totals"]["created"] == 0
    changed = upload(
        admin,
        csv_file(
            line(source="S-1", name="Kiran R. Rao", guardian_name="", guardian_relationship="", guardian_phone="")
        ),
    ).json()
    assert changed["totals"]["changed"] == 1
    assert commit(admin, changed).json()["totals"]["created"] == 0
    assert Student.objects.count() == 4


def test_guardians_are_proposed_without_logins(world, admin):
    job = upload(admin, csv_file(FILE[3])).json()
    commit(admin, job)
    asha = ImportedRecord.objects.get(source_record_id="S-4").student
    link = asha.guardian_links.get()
    assert (link.status, link.source, link.user, link.adult.full_name) == ("proposed", "import", None, "Lata Rao")
    assert not Membership.objects.filter(kind="guardian").exists()


def test_row_imported_by_another_batch_meanwhile(world, admin):
    """Review Focus 3."""
    first = upload(admin, csv_file(FILE[0])).json()
    second = upload(admin, csv_file(FILE[0])).json()
    assert commit(admin, second).json()["totals"]["created"] == 1
    late = commit(admin, first).json()
    assert (late["totals"]["created"], late["totals"]["unchanged"]) == (0, 1)
    assert ImportedRecord.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_commits_at_once_make_one_set(world, on, main, client_for):
    """Review Focus 1."""
    admin = client_for(world.a.slug, world.a_admin)
    job = ImportJob.objects.get(pk=upload(admin, csv_file(FILE[0], FILE[3])).json()["id"])
    results = []

    def go():
        try:
            services.commit(world.a_admin, ImportJob.objects.get(pk=job.pk), job.version)
            results.append("ok")
        except Exception as error:  # noqa: BLE001 — the test reports whatever the losing thread got
            results.append(getattr(error, "status_code", repr(error)))
        finally:
            connection.close()

    threads = [threading.Thread(target=go) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results, key=str) == [409, "ok"]
    assert Student.objects.count() == 2 and ImportedRecord.objects.count() == 2


def test_undo_right_after_commit(world, admin, enrolled):
    people = Person.objects.count()
    job = upload(admin, csv_file(FILE[0], FILE[3])).json()
    committed = commit(admin, job).json()
    assert Student.objects.count() == 3
    undone = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert undone.status_code == 200, undone.json()
    assert undone.json()["status"] == "undone"
    assert (Student.objects.count(), Person.objects.count(), GuardianLink.objects.filter(source="import").count()) == (
        1,
        people,
        0,
    )
    assert not ImportedRecord.objects.exists()
    assert upload(admin, csv_file(FILE[0])).json()["totals"]["valid"] == 1


def test_undo_blocked_once_a_student_changed(world, admin):
    job = upload(admin, csv_file(FILE[0])).json()
    committed = commit(admin, job).json()
    kiran = ImportedRecord.objects.get().student
    record = f"/api/v1/institution/students/{kiran.id}"
    admin.patch(record, {"version": kiran.version, "phone": "+91 90000 44444"}, format="json")
    refused = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "undo_blocked"
    assert kiran.number in refused.json()["detail"]
    assert Student.objects.filter(pk=kiran.pk).exists()


def test_error_file_neutralises_formulas(world, admin):
    bad = [
        line(source=source, born="nope", address="1 Secret Lane", phone="+91 99999 00000")
        for source in ("=cmd", "+1", "-1", "@x")
    ]
    job = upload(admin, csv_file(*bad)).json()
    response = admin.get(f"{URL}/{job['id']}/errors.csv")
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    text = response.content.decode()
    lines = text.strip().splitlines()
    assert lines[0] == "row,column,code,message,source_record_id"
    assert [row.rsplit(",", 1)[1] for row in lines[1:]] == ["'=cmd", "'+1", "'-1", "'@x"]
    assert "Secret" not in text and "99999" not in text


def test_discard_deletes_the_stored_file(world, admin):
    job = upload(admin, csv_file(FILE[0])).json()
    stored = ImportJob.objects.get(pk=job["id"]).file
    path, storage = stored.name, stored.storage
    assert storage.exists(path)
    gone = admin.post(f"{URL}/{job['id']}/discard", {"version": job["version"]}, format="json")
    assert gone.status_code == 200 and gone.json()["status"] == "discarded"
    assert not storage.exists(path)
    assert commit(admin, job).status_code == 409


def test_template_downloads(world, admin):
    response = admin.get(f"{URL}/template.csv")
    assert response.status_code == 200
    lines = response.content.decode().strip().splitlines()
    assert lines[0] == HEADER and len(lines) == 2
