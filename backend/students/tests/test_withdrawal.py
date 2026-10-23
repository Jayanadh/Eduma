"""Withdrawal after enrollment and its reversal (slice 4b S4B-09)."""

import datetime as dt

import pytest

from accounts.permissions import today_for
from accounts.tests.test_auth import host, login
from admissions.tests.test_enrollment import FIRST
from common.models import AuditEvent
from students.models import Enrollment
from testing import factories

OWN = "Own-pass-2027-x"


def url(student, action):
    return f"/api/v1/institution/students/{student.id}/{action}"


@pytest.fixture
def started(world, enrolled):
    """The enrolled student, with an enrollment that began a month ago."""
    Enrollment.objects.filter(student=enrolled).update(entry_date=today_for(world.a) - dt.timedelta(days=30))
    enrolled.refresh_from_db()
    return enrolled


def withdraw(client, student, **changes):
    student.refresh_from_db()
    body = {"version": student.version, "effective_on": str(today_for(student.institution)), "reason": "Family moved."}
    return client.post(url(student, "withdraw"), {**body, **changes}, format="json")


def signed_in_student(world, student):
    client = host(world.a.slug)
    assert login(client, student.user.username, FIRST).status_code == 200
    client.post("/api/v1/session/change-password", {"old_password": FIRST, "new_password": OWN})
    assert client.get("/api/v1/student/me").status_code == 200
    return client


def test_future_date_422(world, started, registrar):
    future = str(today_for(world.a) + dt.timedelta(days=1))
    refused = withdraw(registrar, started, effective_on=future)
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "effective_on"


def test_next_year_enrollment_can_be_cancelled(world, enrolled, registrar):
    """Final review 2: enrolled for next year (entry in the future), the family withdraws now."""
    done = withdraw(registrar, enrolled)
    assert done.status_code == 200, done.json()
    enrollment = enrolled.enrollments.get()
    assert (enrollment.status, enrollment.exit_date) == ("ended", today_for(world.a))


def test_not_before_admission_or_a_started_enrollment(world, started, enrolled, registrar):
    """Review Focus 3, as ruled after the final review: the earliest date is the enrollment's start once it has
    started, else the admission day."""
    before_start = str(today_for(world.a) - dt.timedelta(days=40))
    refused = withdraw(registrar, started, effective_on=before_start)
    error = refused.json()["errors"][0]
    assert (error["field"], error["message"]) == ("effective_on", "That is before the enrollment starts.")
    Enrollment.objects.filter(student=started).update(entry_date=today_for(world.a) + dt.timedelta(days=200))
    early = withdraw(registrar, started, effective_on=str(started.admitted_on - dt.timedelta(days=1)))
    error = early.json()["errors"][0]
    assert (error["field"], error["message"]) == ("effective_on", "That is before the student was admitted.")


def test_reason_required(world, started, registrar):
    assert withdraw(registrar, started, reason="  ").status_code == 422


def test_withdraw_ends_enrollment_and_sign_in(world, started, registrar):
    student_client = signed_in_student(world, started)
    done = withdraw(registrar, started, clearance_note="Library books returned.")
    assert done.status_code == 200, done.json()
    started.refresh_from_db()
    enrollment = started.enrollments.get()
    today = today_for(world.a)
    assert (started.status, started.left_on) == ("withdrawn", today)
    assert (enrollment.status, enrollment.exit_date, enrollment.exit_reason) == ("ended", today, "Family moved.")
    assert done.json()["left_on"] == str(today) and done.json()["can_reinstate"] is True
    assert student_client.get("/api/v1/student/me").status_code in (401, 403)
    assert login(host(world.a.slug), started.user.username, OWN).status_code == 400


def test_withdraw_twice_409_and_stale_409(world, started, registrar):
    stale = registrar.post(
        url(started, "withdraw"),
        {"version": started.version + 3, "effective_on": str(today_for(world.a)), "reason": "x"},
        format="json",
    )
    assert stale.status_code == 409 and stale.json()["code"] == "version_conflict"
    assert withdraw(registrar, started).status_code == 200
    again = withdraw(registrar, started)
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"


def test_reinstate_restores_sign_in(world, started, registrar):
    signed_in_student(world, started)
    withdraw(registrar, started)
    started.refresh_from_db()
    back = registrar.post(url(started, "reinstate"), {"version": started.version}, format="json")
    assert back.status_code == 200, back.json()
    started.refresh_from_db()
    enrollment = started.enrollments.get()
    assert (started.status, started.left_on, enrollment.status, enrollment.exit_date) == (
        "active",
        None,
        "active",
        None,
    )
    assert login(host(world.a.slug), started.user.username, OWN).status_code == 200
    started.refresh_from_db()
    again = registrar.post(url(started, "reinstate"), {"version": started.version}, format="json")
    assert again.status_code == 409


def test_withdraw_needs_student_update(world, started, client_for):
    principal = client_for(world.a.slug, factories.member(world.a, role="principal"))
    assert withdraw(principal, started).status_code == 403


def test_records_and_audit_remain(world, started, registrar):
    withdraw(registrar, started)
    started.refresh_from_db()
    registrar.post(url(started, "reinstate"), {"version": started.version}, format="json")
    actions = set(AuditEvent.objects.filter(object_id=str(started.id)).values_list("action", flat=True))
    assert {"student.withdrawn", "student.reinstated"} <= actions
    assert registrar.get(f"/api/v1/institution/students/{started.id}").status_code == 200
