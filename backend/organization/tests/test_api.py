import pytest

from accounts.models import Membership
from organization.models import Campus
from testing import factories

CAMPUSES = "/api/v1/institution/campuses"
DEPARTMENTS = "/api/v1/institution/departments"


@pytest.fixture
def admin(world, client_for):
    factories.campus(world.a, code="MAIN", name="Main campus")
    return client_for(world.a.slug, world.a_admin)


def main_of(institution) -> Campus:
    return institution.campuses.get(code="MAIN")


def test_members_list_admins_change(world, admin, client_for):
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(CAMPUSES).status_code == 200
    assert teacher.post(CAMPUSES, {"code": "city", "name": "City campus"}).status_code == 403
    created = admin.post(CAMPUSES, {"code": "city", "name": "City campus"})
    assert created.status_code == 201
    assert created.json()["code"] == "CITY"
    duplicate = admin.post(CAMPUSES, {"code": "CITY", "name": "Another"})
    assert duplicate.status_code == 422
    assert duplicate.json()["errors"][0]["field"] == "code"


def test_lists_page_by_five_and_search_from_three_chars(world, admin):
    for n in range(6):
        factories.campus(world.a, code=f"X{n}", name=f"Extra {n}")
    factories.campus(world.a, code="CITY", name="City campus")
    page = admin.get(CAMPUSES).json()
    assert page["count"] == 8 and len(page["results"]) == 5
    assert admin.get(CAMPUSES, {"search": "ci"}).json()["count"] == 8
    assert [c["code"] for c in admin.get(CAMPUSES, {"search": "cit"}).json()["results"]] == ["CITY"]


def test_department_takes_parent_campus_and_rejects_cycles(world, admin):
    city = factories.campus(world.a, code="CITY", name="City campus")
    sci = admin.post(DEPARTMENTS, {"code": "SCI", "name": "Science", "campus": str(main_of(world.a).id)}).json()
    phy = admin.post(DEPARTMENTS, {"code": "PHY", "name": "Physics", "parent": sci["id"], "campus": str(city.id)})
    assert phy.status_code == 201
    assert phy.json()["campus"]["id"] == str(main_of(world.a).id)
    assert phy.json()["parent"] == {"id": sci["id"], "name": "Science"}
    loop = admin.patch(f"{DEPARTMENTS}/{sci['id']}", {"version": sci["version"], "parent": phy.json()["id"]})
    assert loop.status_code == 422
    assert loop.json()["errors"][0]["field"] == "parent"
    itself = admin.patch(f"{DEPARTMENTS}/{sci['id']}", {"version": sci["version"], "parent": sci["id"]})
    assert itself.json()["errors"][0]["field"] == "parent"


def test_other_institution_ids_are_field_errors(world, admin):
    birch_campus = factories.campus(world.b, code="BC")
    birch_dept = factories.department(world.b, code="BD")
    for field, value in (("campus", birch_campus.id), ("parent", birch_dept.id)):
        response = admin.post(DEPARTMENTS, {"code": "X1", "name": "X", field: str(value)})
        assert response.status_code == 422, field
        assert response.json()["errors"][0]["field"] == field


def test_deactivation_refused_while_in_use(world, admin):
    main = main_of(world.a)
    city = factories.campus(world.a, code="CITY", name="City campus")
    sci = factories.department(world.a, code="SCI", campus=city)

    def off(url, record):
        return admin.patch(f"{url}/{record.id}", {"version": record.version, "is_active": False})

    assert off(CAMPUSES, city).json()["code"] == "in_use"
    factories.department(world.a, code="PHY", parent=sci)
    assert off(DEPARTMENTS, sci).json()["code"] == "in_use"
    lang = factories.department(world.a, code="LANG", campus=main)
    factories.assign(Membership.objects.get(user=world.a_admin), "teacher", lang)
    assert off(DEPARTMENTS, lang).json()["code"] == "in_use"
    Campus.objects.filter(pk=city.pk).update(is_active=False)
    response = off(CAMPUSES, main)
    assert response.status_code == 409 and response.json()["code"] == "in_use"


def test_stale_version_is_409(world, admin):
    main = main_of(world.a)
    assert admin.patch(f"{CAMPUSES}/{main.id}", {"version": main.version, "name": "Head office"}).status_code == 200
    stale = admin.patch(f"{CAMPUSES}/{main.id}", {"version": main.version, "name": "Old"})
    assert stale.status_code == 409 and stale.json()["code"] == "version_conflict"


def test_other_hosts_cannot_reach(world, admin, client_for):
    main = main_of(world.a)
    assert client_for(world.b.slug, world.b_admin).get(f"{CAMPUSES}/{main.id}").status_code == 404
    assert client_for(None, world.platform_admin).get(CAMPUSES).status_code == 404


def test_changes_are_audited(world, admin):
    from common.models import AuditEvent

    main = main_of(world.a)
    admin.patch(f"{CAMPUSES}/{main.id}", {"version": main.version, "name": "Head office"})
    event = AuditEvent.objects.get(action="campus.updated")
    assert event.changes == {"name": {"from": "Main campus", "to": "Head office"}}
    assert event.institution_id == world.a.id
