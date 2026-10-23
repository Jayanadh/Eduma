"""Placing students into sections (slice 5a S5A-04, S5A-08, S5A-09)."""

import datetime as dt
import threading

import pytest
from django.db import connection

from academics import placement
from academics.models import EnrollmentPeriod, Section
from accounts.models import Membership, User
from accounts.permissions import today_for
from common.models import AuditEvent
from students import guardians, withdrawal
from testing import factories

from .conftest import API, enrolled_student


def make_section(school, code="6A", capacity=40, year=None):
    return Section.objects.create(
        institution=school.year.institution, year=year or school.year, grade=school.c6, campus=school.main, code=code,
        capacity=capacity,
    )  # fmt: skip


def place(client, section, *students):
    return client.post(
        f"{API}/sections/{section.id}/students", {"students": [str(s.id) for s in students]}, format="json"
    )


def test_full_section_places_nobody(world, admin, school):
    section = make_section(school, capacity=2)
    students = [enrolled_student(world.a, f"2026-000{n}") for n in range(1, 4)]
    refused = place(admin, section, *students)
    assert refused.status_code == 409 and refused.json()["code"] == "section_full"
    assert not EnrollmentPeriod.objects.exists()
    assert place(admin, section, *students[:2]).status_code == 201
    assert EnrollmentPeriod.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_two_placements_race_for_the_last_seat(world, school):
    """Review Focus 1."""
    section = make_section(school, capacity=1)
    students = [enrolled_student(world.a, f"2026-000{n}") for n in (1, 2)]
    results = []

    def go(student):
        try:
            placement.place(world.a_admin, Section.objects.get(pk=section.pk), [student.id])
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
    assert sorted(results) == ["ok", "section_full"]
    assert EnrollmentPeriod.objects.count() == 1


def test_who_can_be_placed(world, admin, school):
    section = make_section(school)
    left = enrolled_student(world.a, "2026-0001")
    left.status = "withdrawn"
    left.save()
    refused = place(admin, section, left)
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "students"
    later = enrolled_student(world.a, "2027-0001", year="2027–28")
    assert place(admin, section, later).status_code == 422
    other = make_section(school, code="6B")
    student = enrolled_student(world.a, "2026-0002")
    assert place(admin, section, student).status_code == 201
    again = place(admin, other, student)
    assert again.status_code == 409 and again.json()["code"] == "already_placed"


def test_moving_within_the_year_is_audited(world, admin, school):
    section, other = make_section(school), make_section(school, code="6B")
    student = enrolled_student(world.a, "2026-0001")
    place(admin, section, student)
    moved = admin.post(
        f"{API}/sections/{section.id}/students/{student.id}/move", {"section": str(other.id)}, format="json"
    )
    assert moved.status_code == 200, moved.json()
    period = EnrollmentPeriod.objects.get()
    assert period.section == other
    event = AuditEvent.objects.get(action="student.section_changed")
    assert event.changes == {"section": {"from": "6A", "to": "6B"}}


def test_withdrawal_ends_and_reinstate_reopens_the_placement(world, admin, school):
    """Review Focus 4."""
    section = make_section(school)
    student = enrolled_student(world.a, "2026-0001")
    student.enrollments.update(entry_date=dt.date(2026, 6, 1))
    place(admin, section, student)
    student.refresh_from_db()
    withdrawal.withdraw(world.a_admin, student, student.version, today_for(world.a), "Moved away")
    assert EnrollmentPeriod.objects.get().state == "ended"
    assert admin.get(f"{API}/sections/{section.id}/students").json() == []
    student.refresh_from_db()
    withdrawal.reinstate(world.a_admin, student, student.version)
    assert EnrollmentPeriod.objects.get().state == "active"


def test_records_show_the_current_section(world, admin, school, client_for):
    section = make_section(school)
    student = enrolled_student(world.a, "2026-0001", name="Kiran Rao")
    place(admin, section, student)
    record = admin.get(f"/api/v1/institution/students/{student.id}").json()
    assert record["current_section"] == "Class 6 · 6A"
    assert record["placements"] == [
        {
            "year": "2026–27",
            "grade": "Class 6",
            "section": "6A",
            "campus": "Main campus",
            "state": "active",
            "is_repeat": False,
        }
    ]
    login = User.objects.create(username="aster.2026-0001", full_name="Kiran Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    student.user = login
    student.save()
    assert client_for(world.a.slug, login).get("/api/v1/student/me").json()["current_section"] == "Class 6 · 6A"
    parent = factories.user(username="lata.rao")
    link = guardians.propose(world.a_admin, student, {"full_name": "Lata Rao"}, "Mother")
    link.user = parent
    link.save()
    link.refresh_from_db()
    guardians.verify(
        world.a_admin, link, link.version, {"authority_basis": "parent", "verification_method": "documents_in_person"}
    )
    child = client_for(world.a.slug, parent).get("/api/v1/family/children").json()[0]
    assert child["current_section"] == "Class 6 · 6A"


def test_rosters_for_managers_and_their_teachers_only(world, admin, school, client_for):
    section = make_section(school)
    place(admin, section, enrolled_student(world.a, "2026-0001", name="Kiran Rao"))
    roster = admin.get(f"{API}/sections/{section.id}/students").json()
    assert [(row["student"]["number"], row["student"]["full_name"]) for row in roster] == [("2026-0001", "Kiran Rao")]
    teacher = factories.member(world.a, role="teacher")
    stranger = factories.member(world.a, role="teacher")
    admin.post(
        f"{API}/sections/{section.id}/teachers",
        {"membership": str(Membership.objects.get(user=teacher).id)},
        format="json",
    )
    assert client_for(world.a.slug, teacher).get(f"{API}/sections/{section.id}/students").status_code == 200
    assert client_for(world.a.slug, stranger).get(f"{API}/sections/{section.id}/students").status_code == 404


def test_placed_imports_cannot_be_undone(world, admin, school):
    from imports.tests.helpers import URL, csv_file, line, upload

    job = upload(admin, csv_file(line(campus_code="MAIN"))).json()
    committed = admin.post(f"{URL}/{job['id']}/commit", {"version": job["version"]}, format="json").json()
    from imports.models import ImportedRecord

    place(admin, make_section(school), ImportedRecord.objects.get().student)
    refused = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert refused.status_code == 409 and "class" in refused.json()["detail"]
