"""Attempts, repeat rules, SGPA/CGPA, transfer credit and degree progress (slice 5d; TST-013, EX-03)."""

import datetime as dt

import pytest

from academics.models import CourseAttempt, CurriculumVersion, Term
from admissions.tests.conftest import switch_on
from common.models import AuditEvent
from testing import factories

from . import college as setup
from .conftest import API


@pytest.fixture
def c(world, on):
    c = setup.build(world.a)
    c.term2 = Term.objects.create(
        year=c.year, name="Semester 2", ordinal=2, starts_on=dt.date(2026, 11, 1), ends_on=dt.date(2027, 3, 31)
    )
    return c


def attempt(c, s, code, gp, term=None, outcome=None, no=1):
    return CourseAttempt.objects.create(
        institution=c.institution, enrollment=s.enrollments.get(), course=c.courses[code], attempt_no=no,
        term=term or c.term, credits=c.courses[code].credits, outcome=outcome or ("passed" if gp >= 4 else "failed"),
        grade_point=gp,
    )  # fmt: skip


def progress(client, s):
    return client.get(f"{API}/students/{s.id}/progress").json()


@pytest.fixture
def seven(c):
    """EX-03: course A (4 credits) at 8, course B (3 credits) at 7."""
    s = setup.student(c, "2026-0001")
    attempt(c, s, "PHY101", 8)
    attempt(c, s, "MAT101", 7)
    return s


def test_the_seven_credit_fixture(admin, c, seven):
    shown = progress(admin, seven)
    assert shown["cgpa"] == "7.57" and shown["terms"][0]["sgpa"] == "7.57"
    assert shown["credits"]["earned"] == "7.0"
    assert shown["advisory"] is True


@pytest.mark.parametrize(
    ("rule", "repeat", "cgpa"),
    [("replace", 9, "8.43"), ("replace", 6, "7.14"), ("best", 6, "7.57"), ("best", 9, "8.43"), ("all", 9, "8.00")],
)
def test_a_repeat_counts_by_the_regulation_rule(admin, c, seven, rule, repeat, cgpa):
    """TST-013: every attempt stays, credits count once, the rule decides the average."""
    CurriculumVersion.objects.filter(pk=c.regulation.pk).update(repeat_rule=rule)
    attempt(c, seven, "MAT101", repeat, term=c.term2, no=2)
    shown = progress(admin, seven)
    assert shown["cgpa"] == cgpa
    assert shown["credits"]["earned"] == "7.0"
    assert [(a["course"], a["attempt_no"]) for a in shown["attempts"] if a["course"] == "MAT101"] == [
        ("MAT101", 1),
        ("MAT101", 2),
    ]
    assert shown["terms"][0]["sgpa"] == "7.57"  # the first semester's result stays as it was


def test_recording_outcomes(world, admin, c, client_for):
    s = setup.student(c, "2026-0001")
    made = attempt(c, s, "PHY101", 0, outcome="in_progress")
    made.grade_point = None
    made.save()
    url = f"{API}/attempts/{made.id}"
    assert admin.patch(url, {"outcome": "passed"}, format="json").status_code == 422
    assert admin.patch(url, {"outcome": "absent", "grade_point": "5"}, format="json").status_code == 422
    assert admin.patch(url, {"outcome": "passed", "grade_point": "11"}, format="json").status_code == 422
    done = admin.patch(url, {"outcome": "passed", "grade_point": "8.5"}, format="json")
    assert done.status_code == 200 and done.json()["outcome"] == "passed"
    corrected = admin.patch(url, {"outcome": "absent"}, format="json")
    assert corrected.json()["grade_point"] is None
    event = AuditEvent.objects.get(action="attempt.outcome_recorded", changes__outcome__to="absent")
    assert event.changes["outcome"] == {"from": "passed", "to": "absent"}
    assert progress(admin, s)["cgpa"] is None  # absent is not a zero
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.patch(url, {"outcome": "passed", "grade_point": "8"}, format="json").status_code == 403
    made.outcome = "withdrawn"
    made.save()
    assert admin.patch(url, {"outcome": "passed", "grade_point": "8"}, format="json").status_code == 409


def test_transfer_credit(admin, c):
    s = setup.student(c, "2026-0001")
    body = {"student": str(s.id), "source_institution": "Elsewhere College", "source_course": "Mechanics I",
            "source_credits": "4", "evidence": "Transcript seen 2026-06-02"}  # fmt: skip
    made = admin.post(f"{API}/transfers", body, format="json")
    assert made.status_code == 201 and made.json()["decision"] == "pending"
    url = f"{API}/transfers/{made.json()['id']}/decide"
    version = made.json()["version"]
    assert admin.post(url, {"version": version, "decision": "approved"}, format="json").status_code == 422
    decided = admin.post(
        url,
        {"version": version, "decision": "approved", "approved_credits": "4", "course": str(c.courses["PHY101"].id),
         "awarding_authority": "Board of Studies, Physics"},
        format="json",
    )  # fmt: skip
    assert decided.status_code == 200, decided.json()
    shown = progress(admin, s)
    assert (shown["credits"]["earned"], shown["credits"]["accepted"]) == ("4.0", "4.0")
    assert {r["code"]: r["status"] for r in shown["courses"]}["PHY101"] == "completed"
    # The credited course now satisfies PHY201's prerequisite.
    assert (
        admin.post(
            f"{API}/registrations", {"student": str(s.id), "offerings": [str(c.phy201.id)]}, format="json"
        ).status_code
        == 201
    )
    other = admin.post(f"{API}/transfers", {**body, "source_course": "Pottery"}, format="json").json()
    admin.post(
        f"{API}/transfers/{other['id']}/decide",
        {"version": other["version"], "decision": "approved", "approved_credits": "2", "awarding_authority": "Dean"},
        format="json",
    )
    shown = progress(admin, s)
    assert (shown["credits"]["earned"], shown["credits"]["accepted"]) == (
        "6.0",
        "4.0",
    )  # unmapped: earned, not toward the award


def test_progress_buckets(admin, c):
    s = setup.student(c, "2026-0001")
    attempt(c, s, "PHY101", 8)
    attempt(c, s, "PHY101L", 3)  # failed
    admin.post(f"{API}/registrations", {"student": str(s.id), "offerings": [str(c.maths.id)]}, format="json")
    shown = progress(admin, s)
    statuses = {r["code"]: r["status"] for r in shown["courses"]}
    assert statuses == {"PHY101": "completed", "PHY101L": "failed", "MAT101": "in_progress", "PHY201": "planned"}
    assert shown["credits"] == {
        "required": "12.0", "earned": "4.0", "accepted": "4.0", "in_progress": "3.0", "planned": "5.0", "unmet": "5.0"
    }  # fmt: skip
    assert shown["cgpa"] == "7.00"  # (4×8 + 1×3) / 5: a fail counts in the average, never in credits
    assert {r["code"]: r["prerequisites_met"] for r in shown["courses"]}["PHY201"] is True


def test_students_see_their_own_progress(world, c, client_for):
    from accounts.models import Membership, User

    s = setup.student(c, "2026-0001")
    attempt(c, s, "PHY101", 8)
    login = User.objects.create_user(username="m.2026-0001", password="Demo-pass-2026", full_name="Learner")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    s.user = login
    s.save()
    mine = client_for(world.a.slug, login).get("/api/v1/student/progress").json()
    assert mine["cgpa"] == "8.00" and mine["regulation"] == "BSC-PHY R2026 rev 1"


def test_isolation(world, admin, c, seven, client_for):
    switch_on(world.b, modules=("admissions", "students", "academics"))
    birch = client_for(world.b.slug, world.b_admin)
    first = CourseAttempt.objects.first()
    assert birch.patch(f"{API}/attempts/{first.id}", {"outcome": "absent"}, format="json").status_code == 404
    assert birch.get(f"{API}/students/{seven.id}/progress").status_code == 404
