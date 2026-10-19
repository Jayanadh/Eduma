"""Slice 4a final review findings, each pinned by a test that failed first."""

import datetime as dt

import pytest

from accounts.models import Membership
from accounts.permissions import has_perm, today_for
from admissions.models import AdmissionCycle, Application
from students.models import Student
from testing import factories

from .conftest import APPS, applicant, complete
from .test_applicant import start, submitted
from .test_enrollment import FIRST
from .test_public_signup import signup
from .test_review import STAFF, act

STAFF_API = "/api/v1/institution/staff"


@pytest.fixture
def asha(world, cycle, client_for):
    return client_for(world.a.slug, applicant(world.a, "asha.parent"))


@pytest.fixture
def registrar(world, client_for):
    return client_for(world.a.slug, factories.member(world.a, role="registrar"))


def to_accepted(world, cycle, asha, registrar):
    application = submitted(asha, cycle).json()
    act(registrar, application, "start-review")
    act(registrar, application, "eligible")
    act(registrar, application, "offer", expires_on=str(today_for(world.a) + dt.timedelta(days=10)))
    mine = asha.get(f"{APPS}/{application['id']}").json()
    asha.post(f"{APPS}/{application['id']}/accept", {"version": mine["version"]}, format="json")
    return application


def test_signup_refuses_student_style_login_ids(world, on):
    """Finding 1: student logins are <slug>.<year>-<n>; nobody may take one first."""
    for taken in ("aster.2027-0001", "birch.2030-12"):
        refused = signup(_host(world), username=taken)
        assert refused.status_code == 422, taken
        assert [error["field"] for error in refused.json()["errors"]] == ["username"]


def test_add_staff_refuses_student_style_login_ids(world, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    body = {
        "full_name": "New Teacher",
        "username": "aster.2027-0009",
        "password": FIRST,
        "role": "teacher",
        "scope_type": "institution",
    }
    refused = admin.post(STAFF_API, body, format="json")
    assert refused.status_code == 422
    assert "username" in {error["field"] for error in refused.json()["errors"]}


def test_enroll_names_a_taken_student_login(world, cycle, asha, registrar):
    """An account made before the rule existed must not leave the registrar with a 'try again' that never works."""
    factories.user(username=f"aster.{cycle['entry_year']}-0001")
    application = to_accepted(world, cycle, asha, registrar)
    refused = act(registrar, application, "enroll", password=FIRST)
    assert refused.status_code == 409
    assert refused.json()["code"] == "login_taken"
    assert f"aster.{cycle['entry_year']}-0001" in refused.json()["detail"]
    assert Student.objects.count() == 0


def test_staff_and_students_cannot_use_applicant_routes(world, cycle, registrar, client_for):
    """Finding 2."""
    student = factories.user(username="aster.someone")
    Membership.objects.create(institution=world.a, user=student, kind="student")
    for client in (registrar, client_for(world.a.slug, student)):
        assert client.get(APPS).status_code == 404
        assert start(client, cycle).status_code == 404


def test_staff_directory_lists_staff_only(world, client_for):
    """Finding 3: applicants and students are not staff, cannot be found, given roles or managed there."""
    parent = applicant(world.a, "asha.parent")
    membership = Membership.objects.get(user=parent)
    admin = client_for(world.a.slug, world.a_admin)
    assert admin.get(STAFF_API, {"search": "asha"}).json()["results"] == []
    assert admin.get(f"{STAFF_API}/{membership.id}").status_code == 404
    give = {"role": "admissions_officer", "scope_type": "institution", "version": membership.version}
    assert admin.post(f"{STAFF_API}/{membership.id}/assignments", give, format="json").status_code == 404


def test_non_staff_hold_no_permissions_even_with_a_role(world, cycle, client_for):
    parent = applicant(world.a, "asha.parent")
    factories.assign(Membership.objects.get(user=parent), "admissions_officer")
    assert not has_perm(parent, world.a, "application.review")
    assert client_for(world.a.slug, parent).get(STAFF).status_code == 403


def test_resubmission_after_the_closing_date(world, cycle, asha, registrar):
    """Finding 4: review runs after the closing date; a family asked for more must still be able to answer."""
    application = submitted(asha, cycle).json()
    act(registrar, application, "request-information", message="A clearer photo, please.")
    AdmissionCycle.objects.filter(pk=cycle["id"]).update(
        status="closed", closes_on=today_for(world.a) - dt.timedelta(days=1)
    )
    mine = asha.get(f"{APPS}/{application['id']}").json()
    saved = asha.patch(f"{APPS}/{application['id']}", complete(mine), format="json").json()
    again = asha.post(f"{APPS}/{application['id']}/submit", {"version": saved["version"]}, format="json")
    assert again.status_code == 200, again.json()
    assert again.json()["stage"] == "submitted"


def test_staff_can_decline_while_waiting_on_the_family(world, cycle, asha, registrar):
    application = submitted(asha, cycle).json()
    act(registrar, application, "request-information", message="A clearer photo, please.")
    declined = act(registrar, application, "reject", reason="No reply after two reminders.")
    assert declined.status_code == 200 and declined.json()["stage"] == "rejected"


def test_an_expired_offer_can_be_made_again_or_declined(world, cycle, client_for, registrar):
    today = today_for(world.a)
    rows = []
    for name in ("asha.parent", "ravi.parent"):
        family = client_for(world.a.slug, applicant(world.a, name))
        application = submitted(family, cycle).json()
        act(registrar, application, "start-review")
        act(registrar, application, "eligible")
        act(registrar, application, "offer", expires_on=str(today + dt.timedelta(days=3)))
        Application.objects.filter(pk=application["id"]).update(offer_expires_on=today - dt.timedelta(days=1))
        rows.append(application)
    assert registrar.get(f"{STAFF}/{rows[0]['id']}").json()["stage"] == "offer_expired"
    assert "offer" in registrar.get(f"{STAFF}/{rows[0]['id']}").json()["actions"]
    again = act(registrar, rows[0], "offer", expires_on=str(today + dt.timedelta(days=7)))
    assert again.status_code == 200 and again.json()["stage"] == "offered"
    declined = act(registrar, rows[1], "reject", reason="The family did not reply.")
    assert declined.status_code == 200 and declined.json()["stage"] == "rejected"


def _host(world):
    from rest_framework.test import APIClient

    return APIClient(HTTP_HOST=f"{world.a.slug}.eduma.test")


def test_missing_items_say_what_is_missing(world, cycle, asha):
    """Finding 6: "Fill this in." six times tells a family nothing."""
    draft = start(asha, cycle).json()
    missing = asha.get(f"{APPS}/{draft['id']}").json()["missing"]
    assert missing["learner_name"] == "Enter the learner's full name."
    assert missing["guardian_phone"] == "Enter the parent or guardian's phone number."
    assert missing["answers.LANG"] == "Answer “Home language”."
    assert len(set(missing.values())) == len(missing)
