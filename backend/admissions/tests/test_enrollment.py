import datetime as dt

import pytest

from accounts.models import Membership, User
from accounts.permissions import today_for
from accounts.tests.test_auth import host, login
from students.models import Enrollment, Person, Student
from testing import factories

from .conftest import APPS, applicant
from .test_applicant import submitted
from .test_review import STAFF, act

FIRST = "Welcome-2027-pass"


@pytest.fixture
def registrar(world, client_for):
    return client_for(world.a.slug, factories.member(world.a, role="registrar"))


@pytest.fixture
def accepted(world, cycle, client_for, registrar):
    family = client_for(world.a.slug, applicant(world.a, "asha.parent"))
    application = submitted(family, cycle).json()
    act(registrar, application, "start-review")
    act(registrar, application, "eligible")
    act(registrar, application, "offer", expires_on=str(today_for(world.a) + dt.timedelta(days=10)))
    mine = family.get(f"{APPS}/{application['id']}").json()
    family.post(f"{APPS}/{application['id']}/accept", {"version": mine["version"]}, format="json")
    return application


def test_enrolling_twice_makes_one_student(world, cycle, accepted, registrar):
    """TST-009."""
    first = act(registrar, accepted, "enroll", password=FIRST)
    assert first.status_code == 200, first.json()
    again = registrar.post(f"{STAFF}/{accepted['id']}/enroll", {"version": 1, "password": FIRST}, format="json")
    assert again.status_code == 200
    assert first.json()["student_id"] == again.json()["student_id"]
    assert (Student.objects.count(), Enrollment.objects.count(), Person.objects.count()) == (1, 1, 2)  # learner, adult
    student = Student.objects.get()
    assert student.number == f"{cycle['entry_year']}-0001" and student.person.full_name == "Meera Rao"
    assert student.application_id is not None
    login_id = f"{world.a.slug}.{student.number}"
    assert User.objects.get(username=login_id).must_change_password
    assert Membership.objects.get(user__username=login_id).kind == "student"


def test_enrolling_needs_an_accepted_offer(world, cycle, client_for, registrar):
    family = client_for(world.a.slug, applicant(world.a, "ravi.parent"))
    application = submitted(family, cycle).json()
    refused = act(registrar, application, "enroll", password=FIRST)
    assert refused.status_code == 409 and Student.objects.count() == 0


def test_weak_first_password_creates_nothing(world, cycle, accepted, registrar):
    """Review Focus 4."""
    weak = act(registrar, accepted, "enroll", password="password")
    assert weak.status_code == 422 and weak.json()["errors"][0]["field"] == "password"
    assert (Student.objects.count(), Person.objects.count()) == (0, 0)


def test_the_student_signs_in_to_their_own_portal(world, cycle, accepted, registrar):
    act(registrar, accepted, "enroll", password=FIRST)
    student = Student.objects.get()
    client = host(world.a.slug)
    assert login(client, f"{world.a.slug}.{student.number}", FIRST).status_code == 200
    client.post("/api/v1/session/change-password", {"old_password": FIRST, "new_password": "Own-pass-2027-x"})
    me = client.get("/api/v1/student/me").json()
    assert me["number"] == student.number and me["enrollment"]["place_label"] == "Class 1"
    assert client.get("/api/v1/institution").status_code == 403
    assert client.get("/api/v1/institution/students").status_code in (403, 404)
    assert login(host(world.b.slug), f"{world.a.slug}.{student.number}", "Own-pass-2027-x").status_code == 400


def test_students_list_scope_search_and_edit(world, cycle, accepted, registrar, client_for):
    act(registrar, accepted, "enroll", password=FIRST)
    student = Student.objects.get()
    listed = registrar.get("/api/v1/institution/students", {"search": "mee"}).json()
    assert [row["number"] for row in listed["results"]] == [student.number]
    detail = registrar.get(f"/api/v1/institution/students/{student.id}").json()
    assert detail["application"]["number"] == accepted["number"]
    url = f"/api/v1/institution/students/{student.id}"
    saved = registrar.patch(url, {"version": detail["version"], "full_name": "Meera R. Rao"}, format="json")
    assert saved.status_code == 200 and saved.json()["full_name"] == "Meera R. Rao"
    assert registrar.patch(url, {"version": detail["version"], "full_name": "Old"}, format="json").status_code == 409
    principal = client_for(world.a.slug, factories.member(world.a, role="principal"))
    assert principal.get(url).status_code == 200
    assert (
        principal.patch(url, {"version": saved.json()["version"], "full_name": "X"}, format="json").status_code == 403
    )
    city = factories.campus(world.a, code="CITY", name="City campus")
    city_principal = client_for(world.a.slug, factories.member(world.a, role="principal", scope=city))
    assert city_principal.get(url).status_code == 404


def test_students_need_the_module(world, client_for):
    assert client_for(world.a.slug, world.a_admin).get("/api/v1/institution/students").status_code == 404
