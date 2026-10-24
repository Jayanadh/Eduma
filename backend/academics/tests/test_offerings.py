"""Course offerings and their teachers (slice 5b S5B-05; spec §7.4, §7.7)."""

import datetime as dt

import pytest

from academics.models import Course, Term
from accounts.models import Membership
from testing import factories

from .conftest import API

CLASSES = "/api/v1/teaching/classes"


@pytest.fixture
def terms(world, school):
    school.physics = factories.department(world.a, code="PHY", name="Physics")
    school.chemistry = factories.department(world.a, code="CHE", name="Chemistry")
    school.t1 = Term.objects.create(
        year=school.year, name="Term 1", ordinal=1, starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2026, 10, 31)
    )
    school.t2 = Term.objects.create(
        year=school.year, name="Term 2", ordinal=2, starts_on=dt.date(2026, 11, 1), ends_on=dt.date(2027, 3, 31)
    )
    school.phy101 = Course.objects.create(
        institution=world.a, code="PHY101", title="Mechanics", credits=4, kind="theory", department=school.physics
    )
    school.lab = Course.objects.create(
        institution=world.a, code="PHY101L", title="Mechanics Lab", credits=1, kind="lab", department=school.physics
    )
    school.che101 = Course.objects.create(
        institution=world.a, code="CHE101", title="Chemistry", credits=4, kind="theory", department=school.chemistry
    )
    school.gen = Course.objects.create(
        institution=world.a, code="GEN101", title="Communication", credits=2, kind="theory"
    )
    return school  # fmt: skip


def offer(client, terms, course=None, term=None, **changes):
    body = {"course": str((course or terms.phy101).id), "term": str((term or terms.t1).id),
            "campus": str(terms.main.id), "code": "A", "capacity": 60, **changes}  # fmt: skip
    return client.post(f"{API}/offerings", body, format="json")


def fields(response):
    return [e["field"] for e in response.json()["errors"]]


def test_offer_and_link(admin, terms):
    lecture = offer(admin, terms)
    assert lecture.status_code == 201, lecture.json()
    lecture = lecture.json()
    assert (lecture["course"]["code"], lecture["term"]["name"], lecture["status"]) == ("PHY101", "Term 1", "planned")
    assert fields(offer(admin, terms)) == ["code"]
    lab = offer(admin, terms, course=terms.lab, code="A1", linked_to=lecture["id"]).json()
    assert lab["linked_to"]["label"] == "PHY101-A"
    later = offer(admin, terms, term=terms.t2).json()
    assert fields(offer(admin, terms, course=terms.lab, code="A2", linked_to=later["id"])) == ["linked_to"]
    itself = admin.patch(
        f"{API}/offerings/{lecture['id']}", {"version": lecture["version"], "linked_to": lecture["id"]}, format="json"
    )
    assert fields(itself) == ["linked_to"]
    loop = admin.patch(
        f"{API}/offerings/{lecture['id']}", {"version": lecture["version"], "linked_to": lab["id"]}, format="json"
    )
    assert fields(loop) == ["linked_to"]
    assert admin.get(f"{API}/offerings/{lecture['id']}").json()["linked"] == ["PHY101L-A1"]


def test_closed_year_and_status(admin, terms):
    made = offer(admin, terms).json()
    url = f"{API}/offerings/{made['id']}"
    opened = admin.patch(url, {"version": made["version"], "status": "open"}, format="json").json()
    closed = admin.patch(url, {"version": opened["version"], "status": "closed"}, format="json").json()
    back = admin.patch(url, {"version": closed["version"], "status": "open"}, format="json")
    assert back.status_code == 409 and back.json()["code"] == "invalid_transition"
    terms.year.status = "closed"
    terms.year.save()
    refused = offer(admin, terms, code="B")
    assert refused.status_code == 409 and refused.json()["code"] == "year_closed"


def test_scope_by_department_else_campus(world, admin, terms, client_for):
    physicist = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=terms.physics))
    assert offer(physicist, terms).status_code == 201
    assert offer(physicist, terms, course=terms.che101).status_code == 403
    city = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=terms.city))
    assert offer(city, terms, course=terms.gen, campus=str(terms.city.id)).status_code == 201
    assert offer(city, terms, course=terms.gen, code="B").status_code == 403


def test_teachers_and_my_classes(world, admin, terms, client_for):
    made = offer(admin, terms).json()
    teacher = factories.member(world.a, role="teacher")
    membership = str(Membership.objects.get(user=teacher).id)
    added = admin.post(f"{API}/offerings/{made['id']}/teachers", {"membership": membership}, format="json")
    assert added.status_code == 201, added.json()
    me = client_for(world.a.slug, teacher)
    assert me.get(CLASSES).json() == [
        {
            "offering": {
                "id": made["id"],
                "course": "PHY101",
                "title": "Mechanics",
                "code": "A",
                "term": "Term 1",
                "year": "2026–27",
            },
            "subjects": [],
            "class_teacher": False,
        }
    ]
    shown = added.json()
    cancelled = admin.patch(
        f"{API}/offerings/{made['id']}", {"version": shown["version"], "status": "cancelled"}, format="json"
    ).json()
    assert [row["membership"]["id"] for row in cancelled["teachers"]] == [membership]
    assert me.get(CLASSES).json() == []
    assert (
        admin.post(f"{API}/offerings/{made['id']}/teachers", {"membership": membership}, format="json").status_code
        == 409
    )
    ended = admin.post(f"{API}/offerings/{made['id']}/teachers/{cancelled['teachers'][0]['id']}/end")
    assert ended.json()["teachers"][0]["in_effect"] is False


def test_list_filters_and_isolation(world, admin, terms, client_for):
    from admissions.tests.conftest import switch_on

    made = offer(admin, terms).json()
    offer(admin, terms, term=terms.t2)
    offer(admin, terms, course=terms.lab, code="A1")
    assert admin.get(f"{API}/offerings", {"term": str(terms.t1.id)}).json()["count"] == 2
    assert admin.get(f"{API}/offerings", {"course": str(terms.lab.id)}).json()["count"] == 1
    other_term = Term.objects.create(
        year=factories_year(world.b), name="T", ordinal=1, starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2026, 9, 1)
    )
    assert fields(offer(admin, terms, term=other_term, code="Z")) == ["term"]
    switch_on(world.b, modules=("admissions", "students", "academics"))
    assert client_for(world.b.slug, world.b_admin).get(f"{API}/offerings/{made['id']}").status_code == 404


def factories_year(institution):
    from academics.models import AcademicYear

    return AcademicYear.objects.create(
        institution=institution, code="2026–27", starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2027, 3, 31)
    )
