import pytest

from accounts.models import Membership, RoleAssignment, User
from common.models import AuditEvent
from testing import factories

STAFF = "/api/v1/institution/staff"


@pytest.fixture
def org(world):
    main = factories.campus(world.a, code="MAIN", name="Main campus")
    city = factories.campus(world.a, code="CITY", name="City campus")
    sci = factories.department(world.a, code="SCI", name="Science", campus=main)
    return main, city, sci


@pytest.fixture
def admin(world, client_for):
    return client_for(world.a.slug, world.a_admin)


def ravi(sci, **changes) -> dict:
    body = {
        "full_name": "Ravi Kumar",
        "username": "ravi.k",
        "email": "",
        "mobile": "",
        "password": "First-pass-2026",
        "role": "teacher",
        "scope_type": "department",
        "department": str(sci.id),
    }
    return {**body, **changes}


def staff_id(user, institution) -> str:
    return str(Membership.objects.get(user=user, institution=institution).id)


def test_admin_adds_staff_with_first_password_and_role(world, org, admin):
    response = admin.post(STAFF, ravi(org[2]), format="json")
    assert response.status_code == 201, response.json()
    person = User.objects.get(username="ravi.k")
    assert person.must_change_password and person.check_password("First-pass-2026")
    assert response.json()["roles"] == [{"label": "Teacher / Faculty", "scope_label": "Science"}]
    assert RoleAssignment.objects.filter(membership__user=person, status="active").count() == 1
    event = AuditEvent.objects.get(action="staff.created")
    assert event.institution_id == world.a.id
    assert "First-pass-2026" not in str(event.changes)


def test_login_id_taken_anywhere_is_a_field_error(world, org, admin):
    before = User.objects.count()
    response = admin.post(STAFF, ravi(org[2], username=world.b_admin.username.upper()), format="json")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "username"
    assert User.objects.count() == before


def test_weak_password_and_missing_scope_refused(world, org, admin):
    weak = admin.post(STAFF, ravi(org[2], password="password"), format="json")
    assert weak.status_code == 422 and weak.json()["errors"][0]["field"] == "password"
    no_campus = admin.post(STAFF, ravi(org[2], scope_type="campus", department=None), format="json")
    assert no_campus.status_code == 422 and no_campus.json()["errors"][0]["field"] == "campus"
    other = factories.campus(world.b, code="BC")
    foreign = admin.post(STAFF, ravi(org[2], scope_type="campus", campus=str(other.id)), format="json")
    assert foreign.json()["errors"][0]["field"] == "campus"
    unknown = admin.post(STAFF, ravi(org[2], role="wizard"), format="json")
    assert unknown.json()["errors"][0]["field"] == "role"
    assert not User.objects.filter(username="ravi.k").exists()


def test_campus_admin_sees_and_adds_only_within_campus(world, org, client_for):
    main, city, sci = org
    boss = factories.member(world.a, role="campus_admin", scope=city)
    city_teacher = factories.member(world.a, role="teacher", scope=city)
    main_teacher = factories.member(world.a, role="teacher", scope=sci)
    client = client_for(world.a.slug, boss)
    listed = {item["id"] for item in client.get(STAFF, {"page_size": 200}).json()["results"]}
    assert listed == {staff_id(boss, world.a), staff_id(city_teacher, world.a)}
    assert client.get(f"{STAFF}/{staff_id(main_teacher, world.a)}").status_code == 404
    assert client.post(STAFF, ravi(sci), format="json").status_code == 403
    admin_at_city = ravi(sci, role="institution_admin", scope_type="campus", campus=str(city.id), department=None)
    refused = client.post(STAFF, admin_at_city, format="json")
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "scope_type"
    teacher_at_city = ravi(sci, scope_type="campus", campus=str(city.id), department=None)
    assert client.post(STAFF, teacher_at_city, format="json").status_code == 201


def test_list_search_and_paging(world, org, admin):
    for n in range(5):
        factories.member(world.a, role="teacher", full_name=f"Teacher {n}")
    admin.post(STAFF, ravi(org[2]), format="json")
    page = admin.get(STAFF).json()
    assert page["count"] == 7 and len(page["results"]) == 5
    assert [i["full_name"] for i in admin.get(STAFF, {"search": "rav"}).json()["results"]] == ["Ravi Kumar"]
    assert admin.get(STAFF, {"search": "ra"}).json()["count"] == 7


def test_edit_details_needs_can_manage_and_version(world, org, admin, client_for):
    created = admin.post(STAFF, ravi(org[2]), format="json").json()
    url = f"{STAFF}/{created['id']}"
    detail = admin.get(url).json()
    assert detail["can_manage"] is True and detail["username"] == "ravi.k"
    assert detail["assignments"][0]["role_label"] == "Teacher / Faculty" and detail["assignments"][0]["in_effect"]
    saved = admin.patch(url, {"version": detail["version"], "full_name": "Ravi K. Kumar"}, format="json")
    assert saved.status_code == 200 and saved.json()["full_name"] == "Ravi K. Kumar"
    stale = admin.patch(url, {"version": detail["version"], "full_name": "Old"}, format="json")
    assert stale.status_code == 409
    own = admin.patch(f"{STAFF}/{staff_id(world.a_admin, world.a)}", {"version": 1, "full_name": "Me"}, format="json")
    assert own.status_code == 403 and own.json()["code"] == "own_membership"
    assert "Change password" in own.json()["detail"]


def test_principal_reads_but_cannot_add(world, org, client_for):
    principal = client_for(world.a.slug, factories.member(world.a, role="principal"))
    assert principal.get(STAFF).status_code == 200
    assert principal.post(STAFF, ravi(org[2]), format="json").status_code == 403
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(STAFF).status_code == 403


def test_roles_come_with_their_phase_on_the_institutions_calendar(world, org, admin):
    """The app groups roles by this, so an ended role never shows as starting later (final review #8)."""
    import datetime as dt

    from accounts.permissions import today_for

    today = today_for(world.a)
    person = factories.member(world.a, role="teacher", scope=org[2])
    membership = Membership.objects.get(user=person)
    factories.assign(membership, "principal", None, starts_on=today + dt.timedelta(days=3))
    week_ago, yesterday = today - dt.timedelta(days=9), today - dt.timedelta(days=1)
    factories.assign(membership, "registrar", None, starts_on=week_ago, ends_on=yesterday)
    rows = admin.get(f"{STAFF}/{membership.id}").json()["assignments"]
    assert {row["role_label"]: row["phase"] for row in rows} == {
        "Teacher / Faculty": "now",
        "Principal / Director": "later",
        "Registrar": "earlier",
    }


def test_staff_list_queries_do_not_grow_with_staff(world, org, admin):
    """Final review #14: one page costs the same number of queries for 5 people or 25."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def queries() -> int:
        with CaptureQueriesContext(connection) as captured:
            assert admin.get(STAFF, {"page_size": 50}).status_code == 200
        return len(captured)

    for _ in range(4):
        factories.member(world.a, role="teacher", scope=org[2])
    few = queries()
    for _ in range(20):
        factories.member(world.a, role="teacher", scope=org[2])
    assert queries() == few


def test_detail_says_whether_the_viewer_may_give_roles(world, org, client_for):
    """Giving a role follows the grant ceiling per role and scope, not rank over the person (final review #9)."""
    city, sci = org[1], org[2]
    boss = client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=city))
    split = factories.member(world.a, role="teacher", scope=city)
    factories.assign(Membership.objects.get(user=split), "teacher", sci)
    detail = boss.get(f"{STAFF}/{staff_id(split, world.a)}").json()
    assert (detail["can_manage"], detail["can_give"]) == (False, True)
    reader = client_for(world.a.slug, factories.member(world.a, role="principal"))
    assert reader.get(f"{STAFF}/{staff_id(split, world.a)}").json()["can_give"] is False
