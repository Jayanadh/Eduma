import datetime as dt

import pytest

from accounts.permissions import today_for
from admissions.models import Application
from testing import factories

from .conftest import APPS, applicant
from .test_applicant import submitted

STAFF = "/api/v1/institution/admissions/applications"


@pytest.fixture
def asha(world, cycle, client_for):
    return client_for(world.a.slug, applicant(world.a, "asha.parent"))


@pytest.fixture
def officer(world, client_for):
    return client_for(world.a.slug, factories.member(world.a, role="admissions_officer"))


@pytest.fixture
def registrar(world, client_for):
    return client_for(world.a.slug, factories.member(world.a, role="registrar"))


def act(client, application, step, **body):
    current = client.get(f"{STAFF}/{application['id']}").json()
    return client.post(f"{STAFF}/{application['id']}/{step}", {"version": current["version"], **body}, format="json")


def test_happy_path_to_an_offer(world, cycle, asha, officer, registrar):
    application = submitted(asha, cycle).json()
    listed = officer.get(STAFF).json()
    assert [row["number"] for row in listed["results"]] == [application["number"]]
    assert act(officer, application, "start-review").json()["stage"] == "under_review"
    assert act(officer, application, "eligible").json()["stage"] == "eligible"
    assert act(officer, application, "offer", expires_on="2099-01-01").status_code == 403  # offers need approval power
    expires = str(today_for(world.a) + dt.timedelta(days=14))
    offered = act(registrar, application, "offer", expires_on=expires)
    assert offered.status_code == 200 and offered.json()["stage"] == "offered"
    mine = asha.get(f"{APPS}/{application['id']}").json()
    assert mine["stage"] == "offered" and mine["offer_expires_on"] == expires
    assert "notes" not in mine


def test_information_requests_reopen_and_keep_the_number(world, cycle, asha, officer):
    application = submitted(asha, cycle).json()
    act(officer, application, "start-review")
    assert act(officer, application, "request-information", message="").status_code == 422
    asked = act(officer, application, "request-information", message="Please upload a clearer photo.")
    assert asked.json()["stage"] == "needs_information"
    mine = asha.get(f"{APPS}/{application['id']}").json()
    assert mine["information_request"] == "Please upload a clearer photo." and "submit" in mine["allowed_actions"]
    again = asha.post(f"{APPS}/{application['id']}/submit", {"version": mine["version"]}, format="json").json()
    assert (again["stage"], again["number"]) == ("submitted", application["number"])
    assert Application.objects.get(pk=application["id"]).revision == 2


def test_seats_are_never_overfilled(world, cycle, client_for, registrar, officer):
    from admissions.models import Place

    Place.objects.filter(pk=cycle["places"][0]["id"]).update(seats=1)
    expires = str(today_for(world.a) + dt.timedelta(days=14))
    rows = []
    for name in ("one.parent", "two.parent"):
        client = client_for(world.a.slug, applicant(world.a, name))
        row = submitted(client, cycle).json()
        act(officer, row, "start-review")
        act(officer, row, "eligible")
        rows.append(row)
    assert act(registrar, rows[0], "offer", expires_on=expires).status_code == 200
    full = act(registrar, rows[1], "offer", expires_on=expires)
    assert full.status_code == 409 and full.json()["code"] == "no_seats"
    Application.objects.filter(pk=rows[0]["id"]).update(offer_expires_on=today_for(world.a) - dt.timedelta(days=1))
    assert act(registrar, rows[1], "offer", expires_on=expires).status_code == 200
    detail = registrar.get(f"/api/v1/institution/admissions/cycles/{cycle['id']}").json()
    assert detail["places"][0]["in_use"] == 1


def test_campus_reviewers_see_their_campus_only(world, cycle, main, asha, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    submitted(asha, cycle)
    city_reviewer = client_for(world.a.slug, factories.member(world.a, role="admissions_officer", scope=city))
    assert city_reviewer.get(STAFF).json()["count"] == 0
    main_reviewer = client_for(world.a.slug, factories.member(world.a, role="admissions_officer", scope=main))
    assert main_reviewer.get(STAFF).json()["count"] == 1


def test_deactivated_campus_stays_reviewable_by_whole_institution_reviewers(world, cycle, main, asha, officer):
    """Review Focus 5."""
    application = submitted(asha, cycle).json()
    type(main).objects.filter(pk=main.pk).update(is_active=False)
    assert officer.get(f"{STAFF}/{application['id']}").status_code == 200


def test_wrong_stage_names_the_current_one(world, cycle, asha, officer, registrar):
    application = submitted(asha, cycle).json()
    response = act(registrar, application, "offer", expires_on="2099-01-01")
    assert response.status_code == 409 and "submitted" in response.json()["detail"].lower()


def test_documents_notes_and_privacy(world, cycle, asha, officer):
    application = submitted(asha, cycle).json()
    detail = officer.get(f"{STAFF}/{application['id']}").json()
    doc = detail["documents"][0]
    rejected = officer.post(
        f"{STAFF}/{application['id']}/documents/{doc['id']}/reject",
        {"version": doc["version"], "note": "Blurred"},
        format="json",
    )
    assert rejected.status_code == 200
    assert (
        officer.post(f"{STAFF}/{application['id']}/notes", {"text": "Called the family."}, format="json").status_code
        == 201
    )
    staff_view = officer.get(f"{STAFF}/{application['id']}").json()
    assert staff_view["notes"][0]["text"] == "Called the family."
    mine = asha.get(f"{APPS}/{application['id']}").json()
    assert "notes" not in mine
    blurred = next(d for d in mine["documents"] if d["id"] == doc["id"])
    assert blurred["status"] == "rejected" and blurred["review_note"] == "Blurred"
    download = officer.get(f"{STAFF}/{application['id']}/documents/{doc['id']}")
    assert download.status_code == 200 and download["Cache-Control"] == "private, no-store"
