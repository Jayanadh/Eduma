import datetime as dt

import pytest
from django.utils import timezone

from accounts.models import Membership, RoleAssignment, User
from common.models import AuditEvent
from testing import factories

from .test_auth import host, login

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


def mid(user, institution) -> str:
    return str(Membership.objects.get(user=user, institution=institution).id)


def only_assignment(user) -> RoleAssignment:
    return RoleAssignment.objects.get(membership__user=user, status="active")


def test_give_role_checks_ceiling_dates_and_scope(world, org, admin):
    main, city, sci = org
    ravi = factories.member(world.a, role="teacher", scope=sci)
    url = f"{STAFF}/{mid(ravi, world.a)}/assignments"
    given = admin.post(url, {"role": "principal", "scope_type": "institution"}, format="json")
    assert given.status_code == 201
    assert {"label": "Principal / Director", "scope_label": "Whole institution"} in given.json()["roles"]
    assert AuditEvent.objects.filter(action="assignment.given").exists()
    backwards = {
        "role": "teacher",
        "scope_type": "campus",
        "campus": str(city.id),
        "starts_on": "2026-11-10",
        "ends_on": "2026-11-01",
    }
    assert admin.post(url, backwards, format="json").json()["errors"][0]["field"] == "ends_on"
    foreign = factories.department(world.b, code="BD")
    hod = {"role": "head_of_department", "scope_type": "department", "department": str(foreign.id)}
    other = admin.post(url, hod, format="json")
    assert other.json()["errors"][0]["field"] == "department"
    at_city = {"role": "institution_admin", "scope_type": "campus", "campus": str(city.id)}
    narrow_admin = admin.post(url, at_city, format="json")
    assert narrow_admin.status_code == 422 and narrow_admin.json()["errors"][0]["field"] == "scope_type"


def test_ended_role_stops_on_next_request(world, org, admin, client_for):
    boss = factories.member(world.a, role="campus_admin", scope=org[1])
    client = client_for(world.a.slug, boss)
    assert client.get(STAFF).status_code == 200
    row = only_assignment(boss)
    ended = admin.post(f"{STAFF}/{mid(boss, world.a)}/assignments/{row.id}/end", {"reason": "Moved"}, format="json")
    assert ended.status_code == 200
    row.refresh_from_db()
    assert (row.status, row.end_reason, row.ended_by) == ("ended", "Moved", world.a_admin)
    assert client.get(STAFF).status_code == 403


def test_nobody_changes_their_own_roles(world, org, admin):
    me = mid(world.a_admin, world.a)
    mine = only_assignment(world.a_admin)
    calls = [
        (f"{STAFF}/{me}/assignments", {"role": "teacher", "scope_type": "institution"}),
        (f"{STAFF}/{me}/assignments/{mine.id}/end", {"reason": "x"}),
        (f"{STAFF}/{me}/password", {"password": "Another-pass-2026"}),
        (f"{STAFF}/{me}/remove", {"reason": "x", "version": 1}),
    ]
    for url, body in calls:
        response = admin.post(url, body, format="json")
        assert response.status_code == 403 and response.json()["code"] == "own_membership", url


def test_last_admin_cannot_go(world, org, client_for):
    second = factories.member(world.a, role="institution_admin")
    second_client = client_for(world.a.slug, second)
    first_row = only_assignment(world.a_admin)
    end_first = f"{STAFF}/{mid(world.a_admin, world.a)}/assignments/{first_row.id}/end"
    assert second_client.post(end_first, {"reason": "Left"}, format="json").status_code == 200
    in_a_month = timezone.localdate() + dt.timedelta(days=30)
    leaving = factories.member(world.a, role="institution_admin", ends_on=in_a_month)
    leaving_client = client_for(world.a.slug, leaving)
    second_row = only_assignment(second)
    end_second = f"{STAFF}/{mid(second, world.a)}/assignments/{second_row.id}/end"
    response = leaving_client.post(end_second, {"reason": "x"}, format="json")
    assert response.status_code == 409 and response.json()["code"] == "last_admin"
    second_detail = leaving_client.get(f"{STAFF}/{mid(second, world.a)}").json()
    body = {"reason": "x", "version": second_detail["version"]}
    removed = leaving_client.post(f"{STAFF}/{mid(second, world.a)}/remove", body, format="json")
    assert removed.status_code == 409 and removed.json()["code"] == "last_admin"


def test_reset_password_forces_change_and_respects_rank(world, org, client_for):
    boss = client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=org[1]))
    teacher = factories.member(world.a, role="teacher", scope=org[1])
    principal = factories.member(world.a, role="principal")
    reset = boss.post(f"{STAFF}/{mid(teacher, world.a)}/password", {"password": "Fresh-pass-2026"}, format="json")
    assert reset.status_code == 204
    teacher.refresh_from_db()
    assert teacher.must_change_password and teacher.check_password("Fresh-pass-2026")
    assert AuditEvent.objects.filter(action="staff.password_reset").exists()
    weak = boss.post(f"{STAFF}/{mid(teacher, world.a)}/password", {"password": "password"}, format="json")
    assert weak.status_code == 422
    refused = boss.post(f"{STAFF}/{mid(principal, world.a)}/password", {"password": "Fresh-pass-2026"})
    assert refused.status_code == 404  # not visible to a Campus Admin at all
    split = factories.member(world.a, role="teacher", scope=org[1])
    factories.assign(Membership.objects.get(user=split), "teacher", org[2])
    outranked = boss.post(f"{STAFF}/{mid(split, world.a)}/password", {"password": "Fresh-pass-2026"})
    assert outranked.status_code == 403  # visible through City, but also a teacher outside it


def test_remove_ends_roles_and_session_restore_gives_none(world, org, admin, client_for):
    ravi = factories.member(world.a, role="teacher", scope=org[2], username="ravi.k")
    session = host(world.a.slug)
    assert login(session, "ravi.k").status_code == 200
    url = f"{STAFF}/{mid(ravi, world.a)}"
    version = admin.get(url).json()["version"]
    removed = admin.post(f"{url}/remove", {"reason": "Left the school", "version": version}, format="json")
    assert removed.status_code == 200 and removed.json()["status"] == "revoked"
    assert set(RoleAssignment.objects.filter(membership__user=ravi).values_list("status", "end_reason")) == {
        ("ended", "Removed from staff")
    }
    assert session.get("/api/v1/session").json()["user"] is None
    assert login(host(world.a.slug), "ravi.k").status_code == 400
    boss = client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=org[1]))
    assert boss.post(f"{url}/restore", {"version": removed.json()["version"]}, format="json").status_code == 404
    restored = admin.post(f"{url}/restore", {"version": removed.json()["version"]}, format="json")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active" and restored.json()["roles"] == []
    assert User.objects.get(username="ravi.k").is_active


def test_roles_that_start_later_count_for_rank_and_visibility(world, org, admin, client_for):
    """A future Institution Admin is out of a Campus Admin's reach now, and a later hire stays visible to whoever
    added them (final review #1, #3)."""
    city = org[1]
    boss = client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=city))
    ravi = factories.member(world.a, role="teacher", scope=city)
    tomorrow = timezone.localdate() + dt.timedelta(days=2)
    factories.assign(Membership.objects.get(user=ravi), "institution_admin", None, starts_on=tomorrow)
    url = f"{STAFF}/{mid(ravi, world.a)}"
    assert boss.get(url).json()["can_manage"] is False
    assert boss.post(f"{url}/password", {"password": "Fresh-pass-2026"}).status_code == 403
    version = boss.get(url).json()["version"]
    assert boss.post(f"{url}/remove", {"reason": "x", "version": version}).status_code == 403
    later = {
        "full_name": "Later Hire",
        "username": "later.hire",
        "password": "First-pass-2026",
        "role": "teacher",
        "scope_type": "campus",
        "campus": str(city.id),
        "starts_on": "2030-01-01",
    }
    created = boss.post(STAFF, later, format="json")
    assert created.status_code == 201
    assert boss.get(f"{STAFF}/{created.json()['id']}").status_code == 200


def test_rank_is_checked_again_under_the_lock(world, org):
    """Final review #6: the view's check could be stale by the time the change runs."""
    from rest_framework.exceptions import PermissionDenied

    from accounts import staff

    boss = factories.member(world.a, role="campus_admin", scope=org[1])
    principal = Membership.objects.get(user=factories.member(world.a, role="principal"))
    with pytest.raises(PermissionDenied):
        staff.remove(boss, principal, "x", principal.version)
    with pytest.raises(PermissionDenied):
        staff.reset_password(boss, principal, "Fresh-pass-2026")
