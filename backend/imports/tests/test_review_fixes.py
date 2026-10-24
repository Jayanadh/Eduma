"""Slice 4c final review findings, each pinned by a test that failed first."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext

from imports.models import ImportedRecord, ImportJob
from students import guardians
from students.models import GuardianLink, Student

from .helpers import HEADER, URL, csv_file, line, upload


def commit(client, job):
    current = client.get(f"{URL}/{job['id']}").json()
    return client.post(f"{URL}/{job['id']}/commit", {"version": current["version"]}, format="json")


def many(count, prefix="S"):
    return [
        line(source=f"{prefix}-{n}", name=f"Learner {prefix}{n}", born=f"2019-01-{n % 28 + 1:02d}")
        for n in range(count)
    ]


def test_undo_keeps_guardians_staff_added(world, on, main, client_for):
    """Finding 1: undo removes what the batch made and nothing else."""
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(line())).json()
    committed = commit(admin, job).json()
    student = ImportedRecord.objects.get().student
    grandma = guardians.propose(world.a_admin, student, {"full_name": "Grandma Rao"}, "Grandmother")
    assert admin.get(f"{URL}/{job['id']}").json()["undo_blocker"]
    refused = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "undo_blocked"
    assert GuardianLink.objects.filter(pk=grandma.pk).exists()


def test_numbers_are_read_once_per_commit(world, on, main, client_for):
    """Finding 4: numbering must not rescan every number for each row."""
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(*many(12))).json()
    with CaptureQueriesContext(connection) as queries:
        assert commit(admin, job).status_code == 200
    scans = [
        q["sql"] for q in queries.captured_queries if '"students_student"."number"' in q["sql"] and "LIKE" in q["sql"]
    ]
    assert len(scans) <= 1
    assert sorted(Student.objects.values_list("number", flat=True)) == [f"2026-{n:04d}" for n in range(1, 13)]


def test_job_page_and_undo_do_not_query_per_student(world, on, main, client_for, django_assert_max_num_queries):
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(*many(15))).json()
    committed = commit(admin, job).json()
    with django_assert_max_num_queries(15):
        admin.get(f"{URL}/{job['id']}")
    with django_assert_max_num_queries(46):  # a fixed number per related table, never per student
        undone = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert undone.status_code == 200 and Student.objects.count() == 0


def test_large_files_are_refused_until_the_job_queue_exists(world, on, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    refused = upload(admin, csv_file(*many(2001)))
    assert refused.status_code == 422 and "2000" in refused.json()["errors"][0]["message"]


def test_source_system_spelling_does_not_matter(world, on, main, client_for):
    """Finding 5."""
    admin = client_for(world.a.slug, world.a_admin)
    first = upload(admin, csv_file(line(born="unknown"))).json()
    commit(admin, first)
    again = upload(admin, csv_file(line(born="unknown")), source_system="  old   erp ").json()
    assert again["totals"]["unchanged"] == 1 and again["source_system"] == "Old ERP"


def test_malformed_or_oversized_values_are_row_or_file_errors(world, on, main, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    long_id = line(source="X" * 101)
    long_email = line(source="S-2", email=("a" * 250) + "@x.example")
    job = upload(admin, csv_file(long_id, long_email))
    assert job.status_code == 201, job.json()
    rows = admin.get(f"{URL}/{job.json()['id']}/rows").json()["results"]
    assert [row["state"] for row in rows] == ["error", "error"]
    broken = SimpleUploadedFile("broken.csv", (HEADER + '\nS-1,"' + "x" * 140000).encode(), "text/csv")
    refused = upload(admin, broken)
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "file"
    assert ImportJob.objects.count() == 1


def test_a_hold_or_registration_since_the_import_blocks_undo(world, on, main, client_for):
    """Slice 5c: holds, registrations and academic records point at imported students; undo refuses, never a 500."""
    from academics.models import Hold

    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(line())).json()
    committed = commit(admin, job).json()
    student = Student.objects.get()
    Hold.objects.create(
        institution=world.a,
        student=student,
        kind="academic",
        reason="x",
        placed_by=world.a_admin,
        placed_on="2026-10-01",
    )
    refused = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "undo_blocked"
