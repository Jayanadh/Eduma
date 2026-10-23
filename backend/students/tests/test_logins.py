"""Giving a student without one a login (slice 4c S4C-12)."""

import datetime as dt

import pytest

from accounts.models import Membership, User
from accounts.permissions import today_for
from admissions.tests.test_enrollment import FIRST
from imports.models import ImportedRecord
from imports.tests.helpers import URL, csv_file, line, upload
from students.models import Enrollment, Person, Student
from testing import factories


@pytest.fixture
def unlinked(world, on):
    person = Person.objects.create(institution=world.a, full_name="Kiran Rao")
    student = Student.objects.create(
        institution=world.a, person=person, number="2026-0001", admitted_on=dt.date(2024, 6, 1)
    )
    Enrollment.objects.create(
        student=student, institution=world.a, academic_year="2026–27", place_code="C2", place_label="Class 2",
        entry_date=dt.date(2026, 6, 1),
    )  # fmt: skip
    return student


def give(client, student, password=FIRST):
    student.refresh_from_db()
    return client.post(
        f"/api/v1/institution/students/{student.id}/login",
        {"version": student.version, "password": password},
        format="json",
    )


def test_gives_a_student_login(world, unlinked, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    done = give(admin, unlinked)
    assert done.status_code == 200, done.json()
    login = User.objects.get(username="aster.2026-0001")
    assert login.must_change_password and login.full_name == "Kiran Rao"
    assert Membership.objects.get(user=login).kind == "student"
    assert done.json()["login"] == "aster.2026-0001"
    again = give(admin, unlinked)
    assert again.status_code == 409


def test_weak_password_creates_nothing(world, unlinked, client_for):
    refused = give(client_for(world.a.slug, world.a_admin), unlinked, password="password")
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "password"
    assert not User.objects.filter(username="aster.2026-0001").exists()


def test_needs_student_update_and_an_active_student(world, unlinked, client_for):
    principal = client_for(world.a.slug, factories.member(world.a, role="principal"))
    assert give(principal, unlinked).status_code == 403
    Student.objects.filter(pk=unlinked.pk).update(status="withdrawn", left_on=today_for(world.a))
    assert give(client_for(world.a.slug, world.a_admin), unlinked).status_code == 409


def test_undo_refused_once_a_login_exists(world, on, main, client_for):
    """Review Focus 5."""
    admin = client_for(world.a.slug, world.a_admin)
    job = upload(admin, csv_file(line())).json()
    committed = admin.post(f"{URL}/{job['id']}/commit", {"version": job["version"]}, format="json").json()
    student = ImportedRecord.objects.get().student
    assert give(admin, student).status_code == 200
    refused = admin.post(f"{URL}/{job['id']}/undo", {"version": committed["version"]}, format="json")
    assert refused.status_code == 409 and "has a login" in refused.json()["detail"]
