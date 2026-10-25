"""Reports and exports (BUILD-11 S11-01..03): rows only within the viewer's scope, permission rechecked on download."""

import datetime as dt

import pytest
from django.utils import timezone

from academics.tests.conftest import enrolled_student
from accounts.models import RoleAssignment
from admissions.tests.conftest import switch_on
from cases import services as cases
from operations import services
from operations.models import ExportJob
from testing import factories

R = "/api/v1/institution/reports"


@pytest.fixture
def r(world, client_for):
    switch_on(world.a, modules=("students", "reports", "services"))
    ns = type("R", (), {})()
    ns.north, ns.south = factories.campus(world.a, name="North"), factories.campus(world.a, name="South")
    for number, place, campus in (
        ("1", "Class 6", ns.north),
        ("2", "Class 6", ns.south),
        ("3", "=HYPERLINK(1)", ns.south),
    ):
        student = enrolled_student(world.a, f"2026-000{number}")
        student.enrollments.update(place_label=place, campus=campus)
    ns.admin = client_for(world.a.slug, world.a_admin)
    reader = factories.custom_role(world.a, permissions=["student.read"])
    ns.north_reader = client_for(world.a.slug, factories.member(world.a, role=None, custom_role=reader, scope=ns.north))
    ns.principal_user = factories.member(world.a, role="principal", username="principal")
    ns.principal = client_for(world.a.slug, ns.principal_user)
    ns.teacher = client_for(world.a.slug, factories.member(world.a, role="teacher", username="teacher"))
    return ns


def rows(client, key):
    return client.get(f"{R}/{key}").json()["rows"]


def test_reports_stay_inside_the_viewers_scope(r):
    assert rows(r.admin, "students_by_class") == [["=HYPERLINK(1)", 1, 0], ["Class 6", 2, 0]]
    assert rows(r.north_reader, "students_by_class") == [["Class 6", 1, 0]]  # South isn't theirs
    report = r.admin.get(f"{R}/students_by_class").json()
    assert report["provenance"]["row_count"] == 2 and report["provenance"]["scope"] == "Only records you may read"
    assert "students_by_class" not in [x["key"] for x in r.teacher.get(f"{R}/").json()]
    assert r.teacher.get(f"{R}/students_by_class").status_code == 403
    assert r.admin.get(f"{R}/fees_outstanding").status_code == 403  # Fees is off
    assert r.admin.get(f"{R}/nonsense").status_code == 404


def test_small_confidential_groups_are_suppressed(world, r):
    for n in range(2):
        cases.open_case(world.a_admin, world.a, "grievance", f"Grievance {n}", "x")
    for n in range(6):
        cases.open_case(world.a_admin, world.a, "service_request", f"Request {n}", "x")
    assert rows(r.admin, "cases_by_type") == [
        ["Academic grievance", "Received", "<5"],
        ["Service request", "Received", 6],
    ]


def test_exports_are_the_requesters_and_recheck_permission(world, r):
    assert r.teacher.post(f"{R}/students_by_class/exports").status_code == 403
    assert r.principal.post(f"{R}/exports").status_code == 405  # the list isn't a way to ask for one
    made = r.principal.post(f"{R}/students_by_class/exports")
    assert made.status_code == 202 and made.json()["state"] == "queued"
    job = made.json()["id"]
    assert r.principal.get(f"{R}/exports/{job}/file").status_code == 409  # not built yet
    services.run_jobs()
    assert r.principal.get(f"{R}/exports").json()[0]["state"] == "done"
    body = b"".join(r.principal.get(f"{R}/exports/{job}/file").streaming_content).decode()
    assert body.splitlines() == ["Class or program,Active,Left", "'=HYPERLINK(1),1,0", "Class 6,2,0"]
    assert r.admin.get(f"{R}/exports/{job}/file").status_code == 403  # only who asked for it
    RoleAssignment.objects.filter(membership__user=r.principal_user).update(ends_on=dt.date(2020, 1, 1))
    assert r.principal.get(f"{R}/exports/{job}/file").status_code in (403, 404)  # access rechecked at download


def test_exports_expire(world, r):
    job = r.principal.post(f"{R}/students_by_class/exports").json()["id"]
    services.run_jobs()
    ExportJob.objects.filter(pk=job).update(expires_at=timezone.now() - dt.timedelta(minutes=1))
    assert r.principal.get(f"{R}/exports/{job}/file").status_code == 410
    from operations.models import JobRun

    JobRun.objects.filter(task="expire_exports").delete()
    services.run_jobs()
    found = ExportJob.objects.get(pk=job)
    assert found.state == "expired" and not found.file


def test_module_gate(world, r):
    switch_on(world.a, modules=("students",))
    assert r.admin.get(f"{R}/").status_code == 404
