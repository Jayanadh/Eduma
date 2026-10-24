"""Rooms, timetable versions, conflicts, substitutions and the teacher's day (slice 6 S6-01..05)."""

import datetime as dt

import pytest

from academics.models import Section, Term
from accounts.models import Membership
from accounts.permissions import today_for
from testing import factories

from .conftest import API


@pytest.fixture
def tt(world, admin, school):
    today = today_for(world.a)
    school.term = Term.objects.create(
        year=school.year,
        name="Term 1",
        ordinal=1,
        starts_on=today - dt.timedelta(days=30),
        ends_on=today + dt.timedelta(days=60),
    )
    school.a = Section.objects.create(
        institution=world.a, year=school.year, grade=school.c6, campus=school.main, code="6A", capacity=40
    )
    school.b = Section.objects.create(
        institution=world.a, year=school.year, grade=school.c6, campus=school.main, code="6B", capacity=40
    )
    school.teacher = factories.member(world.a, role="teacher")
    school.membership = Membership.objects.get(user=school.teacher)
    school.room = admin.post(
        f"{API}/rooms", {"campus": str(school.main.id), "code": "R1", "name": "Lab 1", "capacity": 30}, format="json"
    ).json()
    school.today = today
    return school


def slot(admin, timetable, section, weekday=1, start="09:00", end="09:45", **extra):
    body = {"weekday": weekday, "starts_at": start, "ends_at": end, "section": str(section.id), **extra}
    return admin.post(f"{API}/timetables/{timetable['id']}/slots", body, format="json")


def test_conflicts_block_publishing(admin, tt):
    draft = admin.post(f"{API}/timetables", {"term": str(tt.term.id)}, format="json")
    assert draft.status_code == 201, draft.json()
    draft = draft.json()
    neither = {"weekday": 2, "starts_at": "09:00", "ends_at": "09:45"}
    assert admin.post(f"{API}/timetables/{draft['id']}/slots", neither, format="json").status_code == 422
    slot(admin, draft, tt.a, room=tt.room["id"], teacher=str(tt.membership.id), subject=str(tt.science.id))
    shown = slot(admin, draft, tt.b, start="09:30", end="10:15", room=tt.room["id"]).json()
    assert [c["kind"] for c in shown["conflicts"]] == ["room"]
    refused = admin.post(f"{API}/timetables/{draft['id']}/publish", {"version": shown["version"]}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "timetable_conflict"
    shown = admin.delete(f"{API}/timetables/{draft['id']}/slots/{shown['slots'][1]['id']}").json()
    assert shown["conflicts"] == []
    published = admin.post(
        f"{API}/timetables/{draft['id']}/publish", {"version": shown["version"]}, format="json"
    ).json()
    assert published["status"] == "published"
    assert slot(admin, published, tt.b).status_code == 409
    second = admin.post(f"{API}/timetables", {"term": str(tt.term.id)}, format="json").json()
    assert (second["number"], len(second["slots"])) == (2, 1)
    admin.post(f"{API}/timetables/{second['id']}/publish", {"version": second["version"]}, format="json")
    assert admin.get(f"{API}/timetables/{draft['id']}").json()["status"] == "superseded"
    assert admin.post(f"{API}/timetables/{second['id']}/slots", neither, format="json").status_code == 409


def test_teacher_conflict_and_day_view_with_a_substitute(world, admin, tt, client_for):
    weekday = tt.today.isoweekday()
    draft = admin.post(f"{API}/timetables", {"term": str(tt.term.id)}, format="json").json()
    slot(admin, draft, tt.a, weekday=weekday, teacher=str(tt.membership.id))
    shown = slot(admin, draft, tt.b, weekday=weekday, start="09:15", end="10:00", teacher=str(tt.membership.id)).json()
    assert [c["kind"] for c in shown["conflicts"]] == ["teacher"]
    admin.delete(f"{API}/timetables/{draft['id']}/slots/{shown['slots'][1]['id']}")
    shown = admin.get(f"{API}/timetables/{draft['id']}").json()
    admin.post(f"{API}/timetables/{draft['id']}/publish", {"version": shown["version"]}, format="json")
    me = client_for(world.a.slug, tt.teacher)
    day = me.get("/api/v1/teaching/day", {"date": str(tt.today)}).json()
    assert [(d["target"]["label"], d["substitute"]) for d in day] == [("6A", False)]
    cover = factories.member(world.a, role="teacher")
    made = admin.post(
        f"{API}/substitutions",
        {
            "slot": shown["slots"][0]["id"],
            "date": str(tt.today),
            "teacher": str(Membership.objects.get(user=cover).id),
            "reason": "Training",
        },
        format="json",
    )
    assert made.status_code == 201, made.json()
    assert me.get("/api/v1/teaching/day", {"date": str(tt.today)}).json() == []
    theirs = client_for(world.a.slug, cover).get("/api/v1/teaching/day", {"date": str(tt.today)}).json()
    assert [(d["target"]["label"], d["substitute"]) for d in theirs] == [("6A", True)]
    wrong_day = admin.post(
        f"{API}/substitutions",
        {
            "slot": shown["slots"][0]["id"],
            "date": str(tt.today + dt.timedelta(days=1)),
            "teacher": str(Membership.objects.get(user=cover).id),
            "reason": "x",
        },
        format="json",
    )
    assert wrong_day.status_code == 422
