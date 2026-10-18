from accounts.models import Membership, User
from accounts.tests.test_auth import host
from testing.factories import PASSWORD

from .conftest import CYCLES, cycle_body

PUBLIC = "/api/v1/public/admissions"
SIGNUP = "/api/v1/applicant/signup"


def published(world, main, client_for, **changes):
    admin = client_for(world.a.slug, world.a_admin)
    cycle = admin.post(CYCLES, cycle_body(main, **changes), format="json").json()
    return admin.post(f"{CYCLES}/{cycle['id']}/publish", {"version": cycle["version"]}, format="json").json()


def test_public_page_lists_open_cycles_without_seats(world, on, main, client_for):
    published(world, main, client_for)
    client_for(world.a.slug, world.a_admin).post(CYCLES, cycle_body(main, name="Still a draft"), format="json")
    body = client_for(world.a.slug).get(PUBLIC).json()
    assert body["open"] is True
    assert [c["name"] for c in body["cycles"]] == ["Admissions 2027–28"]
    place = body["cycles"][0]["places"][0]
    assert place == {"id": place["id"], "label": "Class 1", "campus_name": "Main campus"}
    assert body["cycles"][0]["documents"][0] == {"code": "BIRTH", "label": "Birth certificate", "required": True}


def test_public_page_when_admissions_are_off(world, client_for):
    assert client_for(world.a.slug).get(PUBLIC).json() == {"open": False, "cycles": []}
    assert client_for(None).get(PUBLIC).status_code == 404


def signup(client, **changes):
    body = {"full_name": "Asha Parent", "username": "asha.parent", "email": "", "phone": "", "password": PASSWORD}
    return client.post(SIGNUP, {**body, **changes}, format="json")


def test_signup_creates_an_applicant_and_signs_in(world, on):
    client = host(world.a.slug)
    response = signup(client)
    assert response.status_code == 201, response.json()
    assert response.json()["user"]["membership"]["kind"] == "applicant"
    person = User.objects.get(username="asha.parent")
    assert not person.must_change_password
    assert Membership.objects.get(user=person, institution=world.a).kind == "applicant"
    assert client.get("/api/v1/session").json()["user"]["username"] == "asha.parent"
    taken = signup(host(world.a.slug), username=world.b_admin.username)
    assert taken.status_code == 422 and taken.json()["errors"][0]["field"] == "username"
    weak = signup(host(world.a.slug), username="weak.one", password="password")
    assert weak.json()["errors"][0]["field"] == "password"


def test_signup_only_where_admissions_are_open_to_it(world, on):
    assert signup(host(None)).status_code == 404
    world.a.lifecycle_status = "suspended"
    world.a.save()
    assert signup(host(world.a.slug)).status_code == 403
    assert not User.objects.filter(username="asha.parent").exists()


def test_signup_needs_the_module(world):
    assert signup(host(world.a.slug)).status_code == 404
