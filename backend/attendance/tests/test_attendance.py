"""Attendance, corrections, visibility and assignments (slice 6; TST-011)."""

import datetime as dt

import pytest

from academics import sections
from academics.models import Section
from academics.tests.conftest import enrolled_student, school  # noqa: F401 — fixture
from academics.tests.test_placement import place
from accounts.models import Membership, User
from accounts.permissions import today_for
from admissions.tests.conftest import switch_on
from attendance.models import AttendanceMark
from students.models import GuardianLink
from testing import factories

T = "/api/v1/teaching"
I = "/api/v1/institution"  # noqa: E741


@pytest.fixture
def on(world):
    switch_on(world.a, modules=("admissions", "students", "academics", "attendance"))
    return world.a


@pytest.fixture
def admin(world, on, client_for):
    return client_for(world.a.slug, world.a_admin)


@pytest.fixture
def klass(world, admin, school, client_for):  # noqa: F811
    """6A with Kiran (enrolled from June) and Meera (joined yesterday), taught Science by a teacher."""
    today = today_for(world.a)
    section = Section.objects.create(
        institution=world.a, year=school.year, grade=school.c6, campus=school.main, code="6A", capacity=40
    )
    kiran = enrolled_student(world.a, "2026-0001", name="Kiran Rao")
    meera = enrolled_student(world.a, "2026-0002", name="Meera Iyer")
    meera.enrollments.update(entry_date=today - dt.timedelta(days=1))
    place(admin, section, kiran, meera)
    teacher = factories.member(world.a, role="teacher")
    sections.assign_teacher(world.a_admin, section, Membership.objects.get(user=teacher).id, school.science.id)
    return type("K", (), {"section": section, "kiran": kiran, "meera": meera, "teacher": teacher, "today": today,
                          "me": client_for(world.a.slug, teacher)})  # fmt: skip


def session(client, section, date):
    return client.post(f"{T}/attendance", {"section": str(section.id), "date": str(date)}, format="json")


def mark(client, s, *pairs):
    marks = [{"student": str(student.id), "code": code} for student, code in pairs]
    return client.post(f"{T}/attendance/{s['id']}/marks", {"version": s["version"], "marks": marks}, format="json")


def submit(client, s):
    return client.post(f"{T}/attendance/{s['id']}/submit", {"version": s["version"]}, format="json")


def test_only_eligible_roster_dates_count(klass):
    """TST-011: a mid-year joiner is on the roster only from their entry date."""
    k = klass
    earlier = session(k.me, k.section, k.today - dt.timedelta(days=3)).json()
    assert [r["student"]["number"] for r in earlier["roster"]] == ["2026-0001"]
    assert mark(k.me, earlier, (k.meera, "absent")).status_code == 422
    saved = mark(k.me, earlier, (k.kiran, "present")).json()
    submit(k.me, saved)
    now = session(k.me, k.section, k.today).json()
    assert [r["student"]["number"] for r in now["roster"]] == ["2026-0001", "2026-0002"]
    saved = mark(k.me, now, (k.kiran, "late"), (k.meera, "absent")).json()
    assert saved["state"] == "draft"
    submit(k.me, saved)
    meera = k.me.get(f"{I}/students/{k.meera.id}/attendance")
    assert meera.status_code == 403  # a teacher doesn't read records


def test_summaries_count_present_late_and_absent_but_not_unmarked_or_excused(world, admin, klass):
    k = klass
    for days, kiran_code in ((3, "present"), (2, "excused"), (1, "absent")):
        s = session(k.me, k.section, k.today - dt.timedelta(days=days)).json()
        submit(k.me, mark(k.me, s, (k.kiran, kiran_code)).json())
    s = session(k.me, k.section, k.today).json()
    submit(k.me, mark(k.me, s, (k.meera, "present")).json())  # Kiran left unmarked today
    kiran = admin.get(f"{I}/students/{k.kiran.id}/attendance").json()
    assert (kiran["present"], kiran["late"], kiran["absent"], kiran["excused"], kiran["counted"]) == (1, 0, 1, 1, 2)
    assert kiran["percentage"] == "50.0"
    assert [a["code"] for a in kiran["absences"]] == ["absent"]
    meera = admin.get(f"{I}/students/{k.meera.id}/attendance").json()
    assert (meera["counted"], meera["percentage"]) == (1, "100.0")


def test_teacher_scope_and_window(world, admin, klass, client_for):
    k = klass
    other = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert session(other, k.section, k.today).status_code == 404
    old = session(k.me, k.section, k.today - dt.timedelta(days=10))
    assert old.status_code == 422 and old.json()["errors"][0]["field"] == "date"
    assert session(k.me, k.section, k.today + dt.timedelta(days=1)).status_code == 422
    assert session(admin, k.section, k.today - dt.timedelta(days=10)).status_code in (200, 201)
    s = session(k.me, k.section, k.today).json()
    sent = submit(k.me, mark(k.me, s, (k.kiran, "present")).json()).json()
    assert mark(k.me, sent, (k.kiran, "absent")).status_code == 409
    again = session(k.me, k.section, k.today)
    assert again.status_code == 200 and again.json()["id"] == s["id"]


def test_corrections_keep_the_original(world, admin, klass):
    k = klass
    s = session(k.me, k.section, k.today).json()
    sent = submit(k.me, mark(k.me, s, (k.kiran, "absent")).json()).json()
    the_mark = AttendanceMark.objects.get(enrollment__student=k.kiran)
    asked = k.me.post(
        f"{T}/attendance/marks/{the_mark.id}/corrections",
        {"code": "present", "reason": "Was at the nurse"},
        format="json",
    )
    assert asked.status_code == 201, asked.json()
    correction = asked.json()
    assert k.me.post(f"{I}/attendance/corrections/{correction['id']}/approve", {}, format="json").status_code == 403
    pending = admin.get(f"{I}/attendance/corrections").json()
    assert [c["previous_code"] for c in pending] == ["absent"]
    approved = admin.post(f"{I}/attendance/corrections/{correction['id']}/approve", {}, format="json")
    assert approved.json()["state"] == "approved"
    the_mark.refresh_from_db()
    assert the_mark.code == "present"
    assert (approved.json()["previous_code"], approved.json()["new_code"]) == ("absent", "present")
    locked = admin.post(f"{I}/attendance/sessions/{sent['id']}/lock", {"version": sent["version"]}, format="json")
    assert locked.json()["state"] == "locked"
    draft = session(k.me, k.section, k.today - dt.timedelta(days=1)).json()
    mark(k.me, draft, (k.kiran, "absent"))
    draft_mark = AttendanceMark.objects.get(session_id=draft["id"])
    assert (
        k.me.post(
            f"{T}/attendance/marks/{draft_mark.id}/corrections", {"code": "present", "reason": "x"}, format="json"
        ).status_code
        == 409
    )


def test_students_and_shared_guardians_see_attendance(world, admin, klass, client_for):
    k = klass
    s = session(k.me, k.section, k.today).json()
    submit(k.me, mark(k.me, s, (k.kiran, "present")).json())
    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Kiran Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    k.kiran.user = login
    k.kiran.save()
    assert client_for(world.a.slug, login).get("/api/v1/student/attendance").json()["percentage"] == "100.0"
    parent = factories.user(username="rao.parent")
    Membership.objects.create(institution=world.a, user=parent, kind="guardian")
    from students.models import Person

    adult = Person.objects.create(institution=world.a, full_name="Asha Rao")
    link = GuardianLink.objects.create(
        institution=world.a, student=k.kiran, adult=adult, user=parent, relationship="Mother", status="active",
        starts_on=k.today, access_record=False, source="staff",
    )  # fmt: skip
    family = client_for(world.a.slug, parent)
    assert family.get(f"/api/v1/family/children/{k.kiran.id}/attendance").status_code == 404
    link.access_record = True
    link.save()
    assert family.get(f"/api/v1/family/children/{k.kiran.id}/attendance").json()["present"] == 1


def test_assignments(world, admin, klass, client_for):
    k = klass
    due = (dt.datetime.now(dt.UTC) + dt.timedelta(days=2)).isoformat()
    made = k.me.post(
        f"{T}/assignments",
        {"section": str(k.section.id), "title": "Plant cells", "instructions": "Draw one.", "due_at": due},
        format="json",
    )
    assert made.status_code == 201, made.json()
    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Kiran Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    k.kiran.user = login
    k.kiran.save()
    me = client_for(world.a.slug, login)
    mine = me.get("/api/v1/student/assignments").json()
    assert [a["title"] for a in mine] == ["Plant cells"]
    url = f"/api/v1/student/assignments/{made.json()['id']}/submit"
    assert me.post(url, {"text": "First go"}, format="json").status_code == 200
    assert me.post(url, {"text": "Better"}, format="json").json()["submission"]["text"] == "Better"
    shown = k.me.get(f"{T}/assignments/{made.json()['id']}").json()
    assert [(s["student"]["number"], s["late"]) for s in shown["submissions"]] == [("2026-0001", False)]
    fed = k.me.post(
        f"{T}/submissions/{shown['submissions'][0]['id']}/feedback", {"feedback": "Good labels"}, format="json"
    )
    assert fed.status_code == 200
    assert me.post(url, {"text": "Third"}, format="json").status_code == 409
    other = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert other.get(f"{T}/assignments/{made.json()['id']}").status_code == 404


def test_module_gate(world, admin, klass):
    switch_on(world.a, modules=("admissions", "students", "academics"))
    assert session(klass.me, klass.section, klass.today).status_code == 404
