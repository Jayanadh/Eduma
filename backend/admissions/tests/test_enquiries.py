"""Enquiries from first question to application (slice 4c S4C-01 to S4C-04)."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.permissions import today_for
from admissions.models import Enquiry
from common.models import AuditEvent
from testing import factories

from .conftest import applicant, switch_on
from .test_applicant import submitted

PUBLIC = "/api/v1/public/enquiries"
STAFF = "/api/v1/institution/admissions/enquiries"


def visitor(world, slug=None):
    return APIClient(HTTP_HOST=f"{slug or world.a.slug}.eduma.test")


def ask(client, **changes):
    body = {
        "contact_name": "Ravi Kumar",
        "phone": "+91 90000 11111",
        "email": "",
        "learner_name": "Kiran",
        "message": "Is there a school bus to Benz Circle?",
        "website": "",
        **changes,
    }
    return client.post(PUBLIC, body, format="json")


@pytest.fixture
def officer(world, on, client_for):
    return client_for(world.a.slug, factories.member(world.a, role="admissions_officer"))


def test_public_question_becomes_an_enquiry(world, on):
    asked = ask(visitor(world))
    assert asked.status_code == 201
    year = today_for(world.a).year
    assert asked.json() == {"number": f"E{year}-0001"}
    enquiry = Enquiry.objects.get()
    assert (enquiry.source, enquiry.status, enquiry.created_by) == ("website", "open", None)
    assert AuditEvent.objects.filter(action="enquiry.created", object_id=str(enquiry.id)).exists()


def test_honeypot_stores_nothing(world, on):
    assert ask(visitor(world), website="http://spam.example").status_code == 201
    assert Enquiry.objects.count() == 0


def test_phone_or_email_is_needed(world, on):
    refused = ask(visitor(world), phone="", email="")
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "phone"


def test_place_must_be_this_institutions(world, on, cycle, client_for):
    from admissions.models import Place

    birch_campus = factories.campus(world.b, code="B", name="Birch")
    other = Place.objects.create(
        cycle=_birch_cycle(world, birch_campus), code="X", label="X", seats=1, campus=birch_campus
    )
    refused = ask(visitor(world), place=str(other.id))
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "place"
    ours = cycle["places"][0]["id"]
    assert ask(visitor(world), place=ours).status_code == 201


def _birch_cycle(world, campus):
    from admissions.models import AdmissionCycle

    today = today_for(world.b)
    return AdmissionCycle.objects.create(
        institution=world.b, name="Birch", entry_year=today.year + 1, academic_year="x", opens_on=today,
        closes_on=today, status="published",
    )  # fmt: skip


def test_throttled_after_ten(world, on, settings):
    cache.clear()
    client = visitor(world)
    statuses = [ask(client).status_code for _ in range(11)]
    assert statuses[:10] == [201] * 10 and statuses[10] == 429


def test_module_off_is_404(world):
    assert ask(visitor(world)).status_code == 404


def test_staff_list_scope_filters_and_summary(world, on, cycle, officer, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    city_officer = client_for(world.a.slug, factories.member(world.a, role="admissions_officer", scope=city))
    ask(visitor(world), place=cycle["places"][0]["id"])  # a Main-campus place
    ask(visitor(world), contact_name="No place")
    whole = officer.get(STAFF).json()
    assert (
        whole["count"] == 2 and whole["summary"]["status"]["open"] == 2 and whole["summary"]["source"]["website"] == 2
    )
    assert city_officer.get(STAFF).json()["count"] == 0
    assert officer.get(STAFF, {"search": "no place"}).json()["count"] == 1
    assert officer.get(STAFF, {"status": "closed"}).json()["count"] == 0


def test_staff_record_follow_up_assign_and_due(world, on, officer, client_for):
    created = officer.post(
        STAFF, {"contact_name": "Walk-in parent", "phone": "+91 90000 22222", "source": "walk_in"}, format="json"
    )
    assert created.status_code == 201
    enquiry = created.json()
    assert enquiry["source"] == "walk_in" and enquiry["created_by"]
    today = today_for(world.a)
    followed = officer.post(
        f"{STAFF}/{enquiry['id']}/follow-ups",
        {"how": "phone", "note": "Called back about fees.", "next_follow_up_on": str(today)},
        format="json",
    )
    assert followed.status_code == 201 and followed.json()["status"] == "following_up"
    assert officer.get(STAFF, {"due": 1}).json()["count"] == 1
    officer_user = Enquiry.objects.get(pk=enquiry["id"]).follow_ups.get().author
    current = officer.get(f"{STAFF}/{enquiry['id']}").json()
    assigned = officer.patch(
        f"{STAFF}/{enquiry['id']}", {"version": current["version"], "assigned_to": str(officer_user.id)}, format="json"
    )
    assert assigned.status_code == 200 and assigned.json()["assigned_to"]["id"] == str(officer_user.id)
    assert officer.get(STAFF, {"assigned": "me"}).json()["count"] == 1


def test_assignee_must_be_able_to_answer(world, on, officer):
    """Review Focus 4."""
    teacher = factories.member(world.a, role="teacher")
    ask(visitor(world))
    row = Enquiry.objects.get()
    refused = officer.patch(
        f"{STAFF}/{row.id}", {"version": row.version, "assigned_to": str(teacher.id)}, format="json"
    )
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "assigned_to"
    helper = factories.member(world.a, role="admissions_officer")
    assert (
        officer.patch(
            f"{STAFF}/{row.id}", {"version": row.version, "assigned_to": str(helper.id)}, format="json"
        ).status_code
        == 200
    )
    from accounts.models import RoleAssignment

    RoleAssignment.objects.filter(membership__user=helper).update(status="ended")
    shown = officer.get(f"{STAFF}/{row.id}").json()
    assert shown["assigned_to"]["full_name"] == helper.full_name


def test_convert_close_reopen(world, on, cycle, officer, client_for):
    family = client_for(world.a.slug, applicant(world.a, "asha.parent"))
    application = submitted(family, cycle).json()
    ask(visitor(world))
    row = Enquiry.objects.get()
    url = f"{STAFF}/{row.id}"
    assert officer.post(f"{url}/close", {"version": row.version, "reason": " "}, format="json").status_code == 422
    closed = officer.post(f"{url}/close", {"version": row.version, "reason": "No reply"}, format="json").json()
    assert closed["status"] == "closed"
    reopened = officer.post(f"{url}/reopen", {"version": closed["version"]}, format="json").json()
    assert reopened["status"] == "open"
    wrong = officer.post(
        f"{url}/convert", {"version": reopened["version"], "application_number": "A1999-0001"}, format="json"
    )
    assert wrong.status_code == 422 and wrong.json()["errors"][0]["field"] == "application_number"
    done = officer.post(
        f"{url}/convert", {"version": reopened["version"], "application_number": application["number"]}, format="json"
    )
    assert done.status_code == 200 and done.json()["status"] == "converted"
    assert done.json()["application"]["number"] == application["number"]
    again = officer.post(f"{url}/close", {"version": done.json()["version"], "reason": "x"}, format="json")
    assert again.status_code == 409
    stale = officer.post(f"{url}/reopen", {"version": 1}, format="json")
    assert stale.status_code == 409


def test_other_institution_cannot_reach_enquiries(world, on, client_for):
    ask(visitor(world))
    row = Enquiry.objects.get()
    switch_on(world.b)
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(f"{STAFF}/{row.id}").status_code == 404
    assert birch.get(STAFF).json()["count"] == 0
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(STAFF).status_code == 403


def test_convert_needs_same_institution(world, on, officer):
    ask(visitor(world))
    row = Enquiry.objects.get()
    switch_on(world.b)
    from admissions.models import Application

    assert not Application.objects.exists()
    refused = officer.post(
        f"{STAFF}/{row.id}/convert", {"version": row.version, "application_number": "A2027-0001"}, format="json"
    )
    assert refused.status_code == 422


def test_assignees_are_people_who_answer_enquiries(world, on, officer):
    factories.member(world.a, role="registrar", full_name="Rekha Registrar")
    factories.member(world.a, role="teacher", full_name="Tara Teacher")
    names = [person["full_name"] for person in officer.get(f"{STAFF}/assignees").json()]
    assert "Rekha Registrar" in names and world.a_admin.full_name in names
    assert "Tara Teacher" not in names
    assert all(set(person) == {"id", "full_name"} for person in officer.get(f"{STAFF}/assignees").json())
