"""Course registration (slice 5c; TST-010, WF-ACA §6.2, API §4.3)."""

import datetime as dt
import threading

import pytest
from django.db import connection

from academics import registration
from academics.models import CourseAttempt, CourseRegistration, Hold
from accounts.models import Membership
from admissions.tests.conftest import switch_on
from testing import factories

from . import college as setup
from .conftest import API


@pytest.fixture
def c(world, on):
    return setup.build(world.a)


def register(client, student, *offerings, waitlist=False):
    body = {"student": str(student.id), "offerings": [str(o.id) for o in offerings], "waitlist": waitlist}
    return client.post(f"{API}/registrations", body, format="json")


def codes(response):
    return sorted(f["code"] for f in response.json()["failures"])


def act(client, reg, action):
    current = CourseRegistration.objects.get(pk=reg["id"])
    return client.post(f"{API}/registrations/{reg['id']}/{action}", {"version": current.version}, format="json")


def test_a_lecture_and_its_lab_register_together(admin, c):
    s = setup.student(c, "2026-0001")
    alone = register(admin, s, c.lecture)
    assert alone.status_code == 422 and codes(alone) == ["linked_section"]
    assert codes(register(admin, s, c.lab)) == ["linked_section"]
    both = register(admin, s, c.lecture, c.lab)
    assert both.status_code == 201, both.json()
    assert [r["state"] for r in both.json()] == ["registered", "registered"]
    attempts = CourseAttempt.objects.filter(enrollment__student=s).order_by("course__code")
    assert [(a.course.code, a.attempt_no, a.outcome) for a in attempts] == [
        ("PHY101", 1, "in_progress"),
        ("PHY101L", 1, "in_progress"),
    ]
    again = register(admin, s, c.lecture, c.lab)
    assert again.status_code == 200 and CourseRegistration.objects.count() == 2


def test_prerequisites_and_overrides(world, admin, c, client_for):
    s = setup.student(c, "2026-0001")
    refused = register(admin, s, c.phy201)
    assert refused.status_code == 422 and codes(refused) == ["prerequisite"]
    adviser = client_for(world.a.slug, factories.member(world.a, role="academic_adviser"))
    body = {
        "student": str(s.id),
        "offering": str(c.phy201.id),
        "rule": "prerequisite",
        "reason": "Passed Mechanics elsewhere",
        "expires_on": str(c.today + dt.timedelta(days=7)),
    }
    granted = adviser.post(f"{API}/overrides", body, format="json")
    assert granted.status_code == 201, granted.json()
    made = register(admin, s, c.phy201)
    assert made.status_code == 201 and made.json()[0]["state"] == "registered"
    used = made.json()[0]["overrides"]
    assert [(o["rule"], o["reason"], o["regulation"]) for o in used] == [
        ("prerequisite", "Passed Mechanics elsewhere", "R2026 rev 1")
    ]
    assert adviser.post(f"{API}/overrides", {**body, "rule": "capacity_exhausted"}, format="json").status_code == 422
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.post(f"{API}/overrides", body, format="json").status_code == 403


def test_an_override_never_buys_a_seat(world, admin, c):
    c.phy201.capacity = 1
    c.phy201.save()
    first, second = setup.student(c, "2026-0001"), setup.student(c, "2026-0002")
    for s in (first, second):
        registration.grant_override(
            world.a_admin, s, c.phy201, {"rule": "prerequisite", "reason": "Adviser", "expires_on": c.today}
        )
    assert register(admin, first, c.phy201).status_code == 201
    full = register(admin, second, c.phy201)
    assert full.status_code == 409 and full.json()["code"] == "capacity_exhausted"


def test_waitlist_and_promotion(admin, c):
    first, second, third = (setup.student(c, f"2026-000{n}") for n in (1, 2, 3))
    mine = register(admin, first, c.maths).json()[0]
    full = register(admin, second, c.maths)
    assert full.status_code == 409 and full.json()["code"] == "capacity_exhausted"
    waiting = register(admin, second, c.maths, waitlist=True)
    assert waiting.status_code == 201 and waiting.json()[0]["state"] == "waitlisted"
    register(admin, third, c.maths, waitlist=True)
    Hold.objects.create(
        institution=c.institution,
        student=second,
        kind="administrative",
        reason="Fees",
        placed_by=c.institution.memberships.first().user,
        placed_on=c.today,
    )
    dropped = act(admin, mine, "drop")
    assert dropped.json()["state"] == "dropped"
    states = dict(
        CourseRegistration.objects.filter(offering=c.maths).values_list("enrollment__student__number", "state")
    )
    assert states == {"2026-0001": "dropped", "2026-0002": "rejected", "2026-0003": "registered"}
    assert CourseRegistration.objects.get(enrollment__student=second).reason_code == "hold"
    assert not CourseAttempt.objects.filter(enrollment__student=first).exists()
    assert CourseAttempt.objects.filter(enrollment__student=third).count() == 1
    lab_pair = register(admin, first, c.lecture, c.lab, waitlist=True)
    assert lab_pair.status_code == 201  # seats free: waitlist only matters when full


def test_withdrawing_after_the_drop_deadline_keeps_the_attempt(admin, c):
    s = setup.student(c, "2026-0001")
    mine = register(admin, s, c.maths).json()[0]
    c.window.drop_until = c.today - dt.timedelta(days=1)
    c.window.save()
    withdrawn = act(admin, mine, "drop")
    assert withdrawn.json()["state"] == "withdrawn"
    assert CourseAttempt.objects.get(enrollment__student=s).outcome == "withdrawn"


def test_window_hold_regulation_and_credit_limit(world, admin, c):
    s2 = setup.student(c, "2026-0002")
    c.window.max_credits = 4
    c.window.save()
    over = register(admin, s2, c.lecture, c.lab)
    assert codes(over) == ["credit_limit", "credit_limit"]
    Hold.objects.create(
        institution=c.institution, student=s2, kind="academic", reason="Probation", placed_by=world.a_admin,
        placed_on=c.today,
    )  # fmt: skip
    assert codes(register(admin, s2, c.maths)) == ["hold"]
    c.window.closes_on = c.today - dt.timedelta(days=1)
    c.window.save()
    assert codes(register(admin, setup.student(c, "2026-0003"), c.maths)) == ["window_closed"]
    unpinned = setup.student(c, "2026-0004", pinned=False)
    refused = register(admin, unpinned, c.maths)
    assert refused.status_code == 422 and refused.json()["code"] == "no_regulation"


def test_not_in_regulation_and_already_passed(admin, c):
    s = setup.student(c, "2026-0001")
    assert codes(register(admin, s, c.art)) == ["not_in_regulation"]
    CourseAttempt.objects.create(
        institution=c.institution, enrollment=s.enrollments.get(), course=c.courses["MAT101"], attempt_no=1,
        term=c.term, credits=3, outcome="passed", grade_point=8,
    )  # fmt: skip
    assert codes(register(admin, s, c.maths)) == ["already_passed"]


def test_approval_holds_the_seat(world, admin, c):
    c.window.needs_approval = True
    c.window.save()
    first, second = setup.student(c, "2026-0001"), setup.student(c, "2026-0002")
    pending = register(admin, first, c.maths).json()[0]
    assert pending["state"] == "pending_approval" and not CourseAttempt.objects.exists()
    assert register(admin, second, c.maths).json()["code"] == "capacity_exhausted"
    approved = act(admin, pending, "approve")
    assert approved.json()["state"] == "registered" and CourseAttempt.objects.count() == 1
    asked = register(admin, second, c.lecture, c.lab).json()
    rejected = act(admin, asked[0], "reject")
    assert rejected.json()["state"] == "rejected"
    assert CourseRegistration.objects.get(pk=asked[1]["id"]).state == "rejected"  # its lab goes with it
    assert act(admin, rejected.json(), "approve").json()["code"] == "invalid_transition"


@pytest.mark.django_db(transaction=True)
def test_two_students_race_for_the_last_seat(world):
    """TST-010: exactly one registers."""
    switch_on(world.a, modules=("admissions", "students", "academics", "course_registration"))
    c = setup.build(world.a)
    students = [setup.student(c, f"2026-000{n}") for n in (1, 2)]
    results = []

    def go(s):
        try:
            registration.register(world.a_admin, s, [c.maths.id])
            results.append("ok")
        except Exception as error:  # noqa: BLE001 — the losing thread's error is the point
            results.append(getattr(error, "problem_code", repr(error)))
        finally:
            connection.close()

    threads = [threading.Thread(target=go, args=(s,)) for s in students]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == ["capacity_exhausted", "ok"]
    assert CourseRegistration.objects.filter(state="registered").count() == 1


def test_students_register_and_drop_for_themselves(world, c, client_for):
    s = setup.student(c, "2026-0001", name="Ananya Rao")
    from accounts.models import User

    login = User.objects.create_user(username="m.2026-0001", password="Demo-pass-2026", full_name="Ananya Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    s.user = login
    s.save()
    me = client_for(world.a.slug, login)
    page = me.get("/api/v1/student/registration").json()
    assert page["window"]["term"] == "Semester 1"
    offered = {o["label"]: o for o in page["offerings"]}
    assert offered["PHY201-A"]["problems"] == ["prerequisite"] and offered["MAT101-A"]["seats_left"] == 1
    made = me.post("/api/v1/student/registration", {"offerings": [str(c.maths.id)]}, format="json")
    assert made.status_code == 201, made.json()
    reg = made.json()[0]
    assert me.get("/api/v1/student/registration").json()["registrations"][0]["offering"]["label"] == "MAT101-A"
    dropped = me.post(f"/api/v1/student/registrations/{reg['id']}/drop", {"version": reg["version"]}, format="json")
    assert dropped.json()["state"] == "dropped"
    assert (
        me.post(f"{API}/registrations", {"student": str(s.id), "offerings": [str(c.art.id)]}, format="json").status_code
        == 403
    )


def test_teachers_see_their_offering_class_list(world, admin, c, client_for):
    from academics import offerings

    s = setup.student(c, "2026-0001", name="Ananya Rao")
    register(admin, s, c.maths)
    teacher = factories.member(world.a, role="teacher")
    offerings.assign_teacher(world.a_admin, c.maths, Membership.objects.get(user=teacher).id)
    me = client_for(world.a.slug, teacher)
    roster = me.get(f"/api/v1/teaching/offerings/{c.maths.id}/students")
    assert roster.json() == [{"number": "2026-0001", "full_name": "Ananya Rao", "status": "active"}]
    assert me.get(f"/api/v1/teaching/offerings/{c.lecture.id}/students").status_code == 404
    shown = admin.get(f"{API}/offerings/{c.maths.id}").json()
    assert (shown["registered"], shown["waitlisted"]) == (1, 0)


def test_windows_and_holds_api(world, admin, c, client_for):
    url = f"{API}/windows/{c.window.id}"
    patched = admin.patch(url, {"version": c.window.version, "max_credits": "24"}, format="json")
    assert patched.status_code == 200 and patched.json()["max_credits"] == "24.0"
    bad = admin.patch(
        url, {"version": patched.json()["version"], "closes_on": str(c.today - dt.timedelta(days=30))}, format="json"
    )
    assert bad.status_code == 422
    assert (
        admin.post(
            f"{API}/windows",
            {"term": str(c.term.id), "opens_on": str(c.today), "closes_on": str(c.today), "drop_until": str(c.today)},
            format="json",
        ).status_code
        == 422
    )
    s = setup.student(c, "2026-0001")
    hold = admin.post(
        f"{API}/students/{s.id}/holds", {"kind": "administrative", "reason": "Library fine"}, format="json"
    )
    assert hold.status_code == 201
    assert codes(register(admin, s, c.maths)) == ["hold"]
    lifted = admin.post(f"{API}/holds/{hold.json()['id']}/lift", {}, format="json")
    assert lifted.json()["lifted_on"] is not None
    assert register(admin, s, c.maths).status_code == 201
    switch_on(world.b, modules=("admissions", "students", "academics", "course_registration"))
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(f"{API}/registrations", {"student": str(s.id)}).json()["count"] == 0
    assert (
        birch.post(f"{API}/students/{s.id}/holds", {"kind": "academic", "reason": "x"}, format="json").status_code
        == 404
    )
