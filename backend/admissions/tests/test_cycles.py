from common.models import AuditEvent
from testing import factories

from .conftest import CYCLES, cycle_body


def test_admin_creates_edits_and_publishes_a_cycle(world, on, main, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    created = admin.post(CYCLES, cycle_body(main), format="json")
    assert created.status_code == 201, created.json()
    body = created.json()
    year = body["entry_year"]
    assert body["academic_year"] == f"{year}–{str(year + 1)[-2:]}"
    assert [p["label"] for p in body["places"]] == ["Class 1", "Class 6"]
    assert body["places"][0]["in_use"] == 0 and body["status"] == "draft"
    url = f"{CYCLES}/{body['id']}"
    edited = admin.patch(url, {**cycle_body(main, name="Admissions 2027"), "version": body["version"]}, format="json")
    assert edited.status_code == 200 and edited.json()["name"] == "Admissions 2027"
    published = admin.post(f"{url}/publish", {"version": edited.json()["version"]}, format="json")
    assert published.status_code == 200 and published.json()["status"] == "published"
    late = admin.patch(url, {**cycle_body(main), "version": published.json()["version"]}, format="json")
    assert late.status_code == 409 and late.json()["code"] == "invalid_transition"
    closed = admin.post(f"{url}/close", {"version": published.json()["version"]}, format="json")
    assert closed.json()["status"] == "closed"
    assert AuditEvent.objects.filter(action="admission_cycle.published").exists()


def test_publishing_needs_places_and_sane_dates(world, on, main, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    empty = admin.post(CYCLES, cycle_body(main, places=[]), format="json").json()
    refused = admin.post(f"{CYCLES}/{empty['id']}/publish", {"version": empty["version"]}, format="json")
    assert refused.status_code == 422
    backwards = admin.post(CYCLES, cycle_body(main, opens_on="2027-03-01", closes_on="2027-01-01"), format="json")
    assert backwards.status_code == 422 and backwards.json()["errors"][0]["field"] == "closes_on"


def test_bad_lists_are_field_errors(world, on, main, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    body = cycle_body(main)
    body["questions"][0]["kind"] = "essay"
    assert admin.post(CYCLES, body, format="json").json()["errors"][0]["field"].startswith("questions.0")
    body = cycle_body(main)
    body["places"][1]["code"] = "C1"
    assert admin.post(CYCLES, body, format="json").json()["errors"][0]["field"] == "places"
    body = cycle_body(main)
    body["questions"][2]["options"] = ["Only one"]
    assert admin.post(CYCLES, body, format="json").status_code == 422
    other = factories.campus(world.b, code="BC")
    body = cycle_body(main)
    body["places"][0]["campus"] = str(other.id)
    assert admin.post(CYCLES, body, format="json").json()["errors"][0]["field"] == "places.0.campus"


def test_who_may_manage_cycles(world, on, main, client_for):
    officer = client_for(world.a.slug, factories.member(world.a, role="admissions_officer"))
    assert officer.get(CYCLES).status_code == 200
    assert officer.post(CYCLES, cycle_body(main), format="json").status_code == 403
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(CYCLES).status_code == 403
    cycle = client_for(world.a.slug, world.a_admin).post(CYCLES, cycle_body(main), format="json").json()
    assert client_for(world.b.slug, world.b_admin).get(f"{CYCLES}/{cycle['id']}").status_code == 404


def test_module_off_means_no_admissions(world, main, client_for):
    assert client_for(world.a.slug, world.a_admin).get(CYCLES).status_code == 404
