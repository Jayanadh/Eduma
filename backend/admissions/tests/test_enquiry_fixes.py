"""Slice 4c final review findings for enquiries, each pinned by a test that failed first."""

from admissions.models import Enquiry
from testing import factories

from .conftest import CYCLES, cycle_body
from .test_enquiries import PUBLIC, STAFF, ask, visitor


def test_campus_officer_needs_a_place_on_their_campus(world, on, cycle, client_for):
    """Finding 2: refused before saving, not a 500 after it."""
    city = factories.campus(world.a, code="CITY", name="City campus")
    officer = client_for(world.a.slug, factories.member(world.a, role="admissions_officer", scope=city))
    body = {"contact_name": "Walk-in", "phone": "+91 90000 22222", "source": "walk_in", "place": None}
    refused = officer.post(STAFF, body, format="json")
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "place"
    main_place = cycle["places"][0]["id"]
    elsewhere = officer.post(STAFF, {**body, "place": main_place}, format="json")
    assert elsewhere.status_code == 422 and elsewhere.json()["errors"][0]["field"] == "place"
    assert Enquiry.objects.count() == 0


def test_moving_an_enquiry_checks_the_new_place(world, on, cycle, client_for):
    from admissions.models import Place

    city = factories.campus(world.a, code="CITY", name="City campus")
    city_place = Place.objects.create(cycle_id=cycle["id"], code="C1C", label="Class 1 City", campus=city, seats=10)
    admin = client_for(world.a.slug, world.a_admin)
    city_officer = factories.member(world.a, role="admissions_officer", scope=city)
    ask(visitor(world), place=str(city_place.id))
    row = Enquiry.objects.get()
    main_place = cycle["places"][0]["id"]
    refused = admin.patch(
        f"{STAFF}/{row.id}",
        {"version": row.version, "place": main_place, "assigned_to": str(city_officer.id)},
        format="json",
    )
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "assigned_to"
    row.refresh_from_db()
    assert row.place_id == city_place.id and row.assigned_to_id is None
    admin.patch(f"{STAFF}/{row.id}", {"version": row.version, "assigned_to": str(city_officer.id)}, format="json")
    row.refresh_from_db()
    moved = admin.patch(f"{STAFF}/{row.id}", {"version": row.version, "place": main_place}, format="json")
    assert moved.status_code == 422 and moved.json()["errors"][0]["field"] == "assigned_to"


def test_staff_cannot_tie_enquiries_to_draft_cycles(world, on, main, client_for):
    """Finding 3: a draft cycle's places are replaced on every save."""
    admin = client_for(world.a.slug, world.a_admin)
    draft = admin.post(CYCLES, cycle_body(main), format="json").json()
    refused = admin.post(
        STAFF, {"contact_name": "X", "phone": "1", "source": "phone", "place": draft["places"][0]["id"]}, format="json"
    )
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "place"
    saved = admin.patch(f"{CYCLES}/{draft['id']}", {**cycle_body(main), "version": draft["version"]}, format="json")
    assert saved.status_code == 200


def test_public_form_takes_json_only(world, on):
    """Another site's form posting into a visitor's browser must not reach the office."""
    client = visitor(world)
    form = client.post(PUBLIC, "contact_name=Spam&phone=1", content_type="application/x-www-form-urlencoded")
    assert form.status_code == 415
    assert client.post(PUBLIC, {"contact_name": "Spam", "phone": "1"}, format="multipart").status_code == 415
    assert Enquiry.objects.count() == 0
