import pytest

from accounts.models import Membership, RoleAssignment, User
from accounts.permissions import has_perm, today_for
from configuration.models import SettingRevision
from testing import factories

STAFF = "/api/v1/institution/staff"


def approval(institution, on=True, number=1):
    SettingRevision.objects.create(
        institution=institution,
        key="access.role_approval",
        number=number,
        value=on,
        status="published",
        effective_from=today_for(institution),
    )


@pytest.fixture
def city(world):
    return factories.campus(world.a, code="CITY", name="City campus")


@pytest.fixture
def boss(world, city, client_for):
    approval(world.a)
    return client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=city, username="city.boss"))


def mid(user, institution) -> str:
    return str(Membership.objects.get(user=user, institution=institution).id)


def give(client, person, institution, role, scope):
    body = {"role": role, "scope_type": "campus", "campus": str(scope.id)}
    return client.post(f"{STAFF}/{mid(person, institution)}/assignments", body, format="json")


def test_powerful_roles_wait_while_approval_is_on(world, city, boss):
    ravi = factories.member(world.a, role="teacher", scope=city)
    waiting = give(boss, ravi, world.a, "campus_admin", city)
    assert waiting.status_code == 201
    row = RoleAssignment.objects.get(membership__user=ravi, role_key="campus_admin")
    assert row.status == "pending"
    assert not has_perm(ravi, world.a, "membership.assign", ("campus", city.id))
    assert {"phase": "waiting"}.items() <= next(
        a for a in waiting.json()["assignments"] if a["id"] == str(row.id)
    ).items()
    give(boss, ravi, world.a, "teacher", city)
    assert RoleAssignment.objects.filter(membership__user=ravi, role_key="teacher", status="active").count() == 2


def test_requester_cannot_approve(world, city, boss):
    ravi = factories.member(world.a, role="teacher", scope=city)
    give(boss, ravi, world.a, "campus_admin", city)
    row = RoleAssignment.objects.get(membership__user=ravi, role_key="campus_admin")
    own = boss.post(f"{STAFF}/{mid(ravi, world.a)}/assignments/{row.id}/approve")
    assert own.status_code == 403 and own.json()["code"] == "own_request"


def test_admin_approves_and_it_takes_effect(world, city, boss, client_for):
    ravi = factories.member(world.a, role="teacher", scope=city)
    give(boss, ravi, world.a, "campus_admin", city)
    row = RoleAssignment.objects.get(membership__user=ravi, role_key="campus_admin")
    admin = client_for(world.a.slug, world.a_admin)
    detail = admin.get(f"{STAFF}/{mid(ravi, world.a)}").json()
    assert next(a for a in detail["assignments"] if a["id"] == str(row.id))["can_decide"] is True
    assert admin.post(f"{STAFF}/{mid(ravi, world.a)}/assignments/{row.id}/approve").status_code == 200
    row.refresh_from_db()
    assert (row.status, row.starts_on, row.decided_by) == ("active", today_for(world.a), world.a_admin)
    assert has_perm(ravi, world.a, "membership.assign", ("campus", city.id))


def test_reject_ends_with_reason(world, city, boss, client_for):
    ravi = factories.member(world.a, role="teacher", scope=city)
    give(boss, ravi, world.a, "campus_admin", city)
    row = RoleAssignment.objects.get(membership__user=ravi, role_key="campus_admin")
    admin = client_for(world.a.slug, world.a_admin)
    url = f"{STAFF}/{mid(ravi, world.a)}/assignments/{row.id}/reject"
    assert admin.post(url, {"reason": ""}, format="json").status_code == 422
    assert admin.post(url, {"reason": "One is enough"}, format="json").status_code == 200
    row.refresh_from_db()
    assert (row.status, row.end_reason, row.decided_by) == ("ended", "One is enough", world.a_admin)


def test_turning_approval_off_keeps_waiting_requests(world, city, boss, client_for):
    ravi = factories.member(world.a, role="teacher", scope=city)
    give(boss, ravi, world.a, "campus_admin", city)
    approval(world.a, on=False, number=2)
    row = RoleAssignment.objects.get(membership__user=ravi, role_key="campus_admin")
    assert row.status == "pending"
    admin = client_for(world.a.slug, world.a_admin)
    assert admin.post(f"{STAFF}/{mid(ravi, world.a)}/assignments/{row.id}/approve").status_code == 200


def test_removing_a_person_ends_their_requests(world, city, boss, client_for):
    ravi = factories.member(world.a, role="teacher", scope=city)
    give(boss, ravi, world.a, "campus_admin", city)
    admin = client_for(world.a.slug, world.a_admin)
    version = admin.get(f"{STAFF}/{mid(ravi, world.a)}").json()["version"]
    admin.post(f"{STAFF}/{mid(ravi, world.a)}/remove", {"reason": "Left", "version": version}, format="json")
    row = RoleAssignment.objects.get(membership__user=ravi, role_key="campus_admin")
    assert (row.status, row.end_reason) == ("ended", "Removed from staff")


def test_add_staff_with_a_powerful_role_waits(world, city, boss):
    body = {
        "full_name": "New Head",
        "username": "new.head",
        "password": "First-pass-2026",
        "role": "campus_admin",
        "scope_type": "campus",
        "campus": str(city.id),
    }
    assert boss.post(STAFF, body, format="json").status_code == 201
    person = User.objects.get(username="new.head")
    assert RoleAssignment.objects.get(membership__user=person).status == "pending"
    created = boss.get(STAFF, {"search": "new"}).json()["results"]
    assert [p["username"] for p in created] == ["new.head"]  # the requester still sees whom they added


def test_approvals_list_shows_what_the_caller_may_decide(world, city, boss, client_for):
    ravi = factories.member(world.a, role="teacher", scope=city)
    give(boss, ravi, world.a, "campus_admin", city)
    admin = client_for(world.a.slug, world.a_admin)
    listed = admin.get("/api/v1/institution/approvals").json()
    assert [(r["person"], r["role_label"], r["requested_by_name"]) for r in listed["roles"]] == [
        (ravi.full_name, "Campus Admin", User.objects.get(username="city.boss").full_name)
    ]
    assert boss.get("/api/v1/institution/approvals").json() == {"roles": [], "settings": []}
