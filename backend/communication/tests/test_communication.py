"""Messages, notifications, calls and teacher-led classes (slice 9; TST-017, TST-018)."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from academics import sections
from academics.models import Section
from academics.tests.conftest import enrolled_student, on, school  # noqa: F401 — fixtures
from academics.tests.test_placement import place
from accounts.models import Membership, User
from admissions.tests.conftest import switch_on
from communication.models import ClassSession
from students.models import GuardianLink, Person
from testing import factories

C = "/api/v1/communication"


def guardian(world, student, username, messages=True):
    login = factories.user(username=username)
    Membership.objects.create(institution=world.a, user=login, kind="guardian")
    adult = Person.objects.create(institution=world.a, full_name=username.title())
    return GuardianLink.objects.create(
        institution=world.a,
        student=student,
        adult=adult,
        user=login,
        relationship="Mother",
        status="active",
        starts_on=dt.date(2026, 1, 1),
        access_record=True,
        access_messages=messages,
        source="staff",
    )


@pytest.fixture
def k(world, client_for, school):  # noqa: F811
    switch_on(world.a, modules=("admissions", "students", "academics", "communication"))
    admin = client_for(world.a.slug, world.a_admin)
    section = Section.objects.create(
        institution=world.a, year=school.year, grade=school.c6, campus=school.main, code="6A", capacity=40
    )
    kiran, other = (
        enrolled_student(world.a, "2026-0001", name="Kiran Rao"),
        enrolled_student(world.a, "2026-0002", name="Other"),
    )
    place(admin, section, kiran, other)
    teacher = factories.member(world.a, role="teacher", username="sci.teacher")
    sections.assign_teacher(world.a_admin, section, Membership.objects.get(user=teacher).id, school.science.id)
    ns = type("K", (), {})()
    ns.section, ns.kiran, ns.other, ns.admin = section, kiran, other, admin
    ns.teacher_user, ns.teacher = teacher, client_for(world.a.slug, teacher)
    ns.link = guardian(world, kiran, "kiran.parent")
    ns.parent = client_for(world.a.slug, ns.link.user)
    ns.stranger = client_for(world.a.slug, guardian(world, other, "other.parent").user)
    return ns


def start(client, student, teacher, text="Hello", client_id="m1"):
    body = {
        "student": str(student.id),
        "with": str(teacher.id),
        "subject": "Science homework",
        "body": text,
        "client_id": client_id,
    }
    return client.post(f"{C}/conversations", body, format="json")


def say(client, conversation, text, client_id):
    return client.post(
        f"{C}/conversations/{conversation}/messages", {"body": text, "client_id": client_id}, format="json"
    )


def test_a_linked_guardian_and_the_teacher_talk_and_strangers_cannot(world, k):
    """TST-017 (messaging)."""
    made = start(k.parent, k.kiran, k.teacher_user)
    assert made.status_code == 201, made.json()
    conversation = made.json()["id"]
    assert start(k.stranger, k.kiran, k.teacher_user).status_code == 404  # not their child
    assert k.stranger.get(f"{C}/conversations/{conversation}").status_code == 404
    first = say(k.teacher, conversation, "Thanks, I'll look", "t1")
    again = say(k.teacher, conversation, "Thanks, I'll look", "t1")
    assert (
        first.status_code == 201 and again.status_code == 200 and again.json()["sequence"] == first.json()["sequence"]
    )
    thread = k.parent.get(f"{C}/conversations/{conversation}").json()
    assert [m["body"] for m in thread["messages"]] == ["Hello", "Thanks, I'll look"]
    assert thread["unread"] == 1
    k.parent.post(f"{C}/conversations/{conversation}/read", {"sequence": 2}, format="json")
    assert k.parent.get(f"{C}/conversations").json()[0]["unread"] == 0
    teacher_inbox = k.teacher.get(f"{C}/notifications").json()
    assert [n["text"][:15] for n in teacher_inbox] == ["New message abo"]


def test_losing_the_relationship_closes_the_thread(world, k):
    conversation = start(k.parent, k.kiran, k.teacher_user).json()["id"]
    k.link.access_messages = False
    k.link.save()
    assert k.parent.get(f"{C}/conversations/{conversation}").status_code == 404
    assert say(k.parent, conversation, "Still there?", "p2").status_code == 404
    assert k.parent.get(f"{C}/conversations").json() == []
    k.link.access_messages = True
    k.link.save()
    assert start(k.parent, k.kiran, k.teacher_user, client_id="m9").status_code == 201


def test_guardians_starting_follows_the_policy(world, k):
    assert (
        k.admin.put(
            f"{C}/policy", {"guardians_can_start": False, "calls_enabled": True, "classes_enabled": True}, format="json"
        ).status_code
        == 200
    )
    assert start(k.parent, k.kiran, k.teacher_user).status_code == 403
    teacher_start = k.teacher.post(
        f"{C}/conversations",
        {
            "student": str(k.kiran.id),
            "with": str(k.link.user.id),
            "subject": "Lab safety",
            "body": "A note",
            "client_id": "t0",
        },
        format="json",
    )
    assert teacher_start.status_code == 201
    assert len(teacher_start.json()["participants"]) == 2


def test_quiet_hours_delay_notifications_and_calls(world, k):
    now = timezone.localtime(timezone=ZoneInfo(world.a.timezone))
    k.parent.put(
        f"{C}/preferences",
        {
            "quiet_from": (now - dt.timedelta(hours=1)).strftime("%H:%M"),
            "quiet_until": (now + dt.timedelta(hours=1)).strftime("%H:%M"),
        },
        format="json",
    )
    conversation = k.teacher.post(
        f"{C}/conversations",
        {
            "student": str(k.kiran.id),
            "with": str(k.link.user.id),
            "subject": "Tomorrow",
            "body": "Bring a notebook",
            "client_id": "t1",
        },
        format="json",
    ).json()["id"]
    assert k.parent.get(f"{C}/notifications").json() == []  # held until quiet hours end
    call = k.teacher.post(f"{C}/calls", {"conversation": conversation}, format="json")
    assert call.status_code == 409 and call.json()["code"] == "unavailable"


def test_calls(world, k, client_for):
    """TST-017 (calling): the right people may call; the provider must exist; stale answers fail."""
    conversation = start(k.parent, k.kiran, k.teacher_user).json()["id"]
    ringing = k.teacher.post(f"{C}/calls", {"conversation": conversation}, format="json")
    assert ringing.status_code == 201 and ringing.json()["state"] == "ringing"
    unconfigured = k.parent.post(f"{C}/calls/{ringing.json()['id']}/accept", {}, format="json")
    assert unconfigured.status_code == 409 and unconfigured.json()["code"] == "integration_not_configured"
    k.admin.put(f"{C}/media", {"provider": "sandbox", "secret": "media-test-secret"}, format="json")
    second = k.teacher.post(f"{C}/calls", {"conversation": conversation}, format="json").json()
    accepted = k.parent.post(f"{C}/calls/{second['id']}/accept", {}, format="json")
    assert accepted.json()["state"] == "connected" and accepted.json()["token"]["role"] == "participant"
    assert k.parent.post(f"{C}/calls/{second['id']}/accept", {}, format="json").status_code == 409  # another device
    k.teacher.post(f"{C}/calls/{second['id']}/end", {}, format="json")
    assert k.parent.post(f"{C}/calls/{second['id']}/accept", {}, format="json").status_code == 409  # stale push
    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Kiran Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    student = client_for(world.a.slug, login)
    assert student.post(f"{C}/calls", {"conversation": conversation}, format="json").status_code == 404


def test_a_class_never_runs_without_its_teacher(world, k, client_for):
    """TST-018."""
    k.admin.put(f"{C}/media", {"provider": "sandbox", "secret": "media-test-secret"}, format="json")
    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Kiran Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    k.kiran.user = login
    k.kiran.save()
    student = client_for(world.a.slug, login)
    made = k.teacher.post(
        f"{C}/classes",
        {"section": str(k.section.id), "title": "Revision", "starts_at": timezone.now().isoformat()},
        format="json",
    )
    assert made.status_code == 201, made.json()
    session = made.json()["id"]
    assert (
        student.post(
            f"{C}/classes",
            {"section": str(k.section.id), "title": "Mine", "starts_at": timezone.now().isoformat()},
            format="json",
        ).status_code
        == 404
    )
    assert student.post(f"{C}/classes/{session}/join", {}, format="json").json()["code"] == "not_started"
    host = k.teacher.post(f"{C}/classes/{session}/join", {}, format="json").json()
    assert host["token"]["role"] == "host" and host["session"]["state"] == "live"
    waiting = student.post(f"{C}/classes/{session}/join", {}, format="json")
    assert waiting.status_code == 202 and waiting.json()["admission"] == "waiting" and waiting.json()["token"] is None
    participant = waiting.json()["participant"]
    k.teacher.post(f"{C}/classes/{session}/participants/{participant}/admit", {}, format="json")
    inside = student.post(f"{C}/classes/{session}/join", {}, format="json").json()
    assert inside["admission"] == "admitted" and inside["token"]["role"] == "attendee"
    assert (
        k.teacher.post(f"{C}/media/verify", {"token": inside["token"]["value"]}, format="json").json()["valid"] is True
    )
    k.teacher.post(f"{C}/classes/{session}/participants/{participant}/remove", {}, format="json")
    assert (
        k.teacher.post(f"{C}/media/verify", {"token": inside["token"]["value"]}, format="json").json()["valid"] is False
    )
    assert student.post(f"{C}/classes/{session}/join", {}, format="json").status_code == 403
    k.teacher.post(f"{C}/classes/{session}/leave", {}, format="json")
    assert k.teacher.get(f"{C}/classes/{session}").json()["state"] == "paused"
    ClassSession.objects.filter(pk=session).update(paused_at=timezone.now() - dt.timedelta(seconds=30))
    k.teacher.post(f"{C}/classes/{session}/join", {}, format="json")
    assert k.teacher.get(f"{C}/classes/{session}").json()["state"] == "live"  # back within the grace
    k.teacher.post(f"{C}/classes/{session}/leave", {}, format="json")
    ClassSession.objects.filter(pk=session).update(paused_at=timezone.now() - dt.timedelta(seconds=61))
    shown = k.teacher.get(f"{C}/classes/{session}").json()
    assert shown["state"] == "ended" and shown["recording"] is False
    assert k.teacher.post(f"{C}/classes/{session}/join", {}, format="json").json()["code"] == "ended"


def test_family_fees_follow_their_own_permission(world, k):
    switch_on(world.a, modules=("admissions", "students", "academics", "communication", "fees"))
    assert k.parent.get(f"/api/v1/family/children/{k.kiran.id}/fees").status_code == 404  # access_fees is off
    k.link.access_fees = True
    k.link.save()
    assert k.parent.get(f"/api/v1/family/children/{k.kiran.id}/fees").status_code == 200


def test_module_gate_and_isolation(world, k, client_for):
    conversation = start(k.parent, k.kiran, k.teacher_user).json()["id"]
    switch_on(world.b, modules=("students", "communication"))
    assert client_for(world.b.slug, world.b_admin).get(f"{C}/conversations/{conversation}").status_code == 404
    switch_on(world.a, modules=("admissions", "students", "academics"))
    assert k.parent.get(f"{C}/conversations").status_code == 404
