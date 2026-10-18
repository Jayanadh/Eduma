import datetime as dt

from django.utils import timezone

from accounts.models import Membership, RoleAssignment
from accounts.permissions import WHOLE, can_assign, can_manage_person, has_perm
from accounts.roles import BUILTIN_ROLES, PERMISSIONS
from testing import factories

from .test_auth import host, login


def membership_of(user, institution):
    return Membership.objects.get(user=user, institution=institution)


def org(institution):
    """City campus with one department, Main campus with SCI > PHY and LANG."""
    main = institution.campuses.get(code="MAIN") if institution.campuses.filter(code="MAIN").exists() else None
    main = main or factories.campus(institution, code="MAIN", name="Main campus")
    city = factories.campus(institution, code="CITY", name="City campus")
    city_dept = factories.department(institution, code="CTY-ART", name="City arts", campus=city)
    sci = factories.department(institution, code="SCI", name="Science", campus=main)
    phy = factories.department(institution, code="PHY", name="Physics", parent=sci)
    lang = factories.department(institution, code="LANG", name="Languages", campus=main)
    return main, city, city_dept, sci, phy, lang


def test_builtin_admin_holds_every_registered_permission():
    assert BUILTIN_ROLES["institution_admin"].permissions == frozenset(PERMISSIONS)
    for role in BUILTIN_ROLES.values():
        assert role.permissions <= set(PERMISSIONS)


def test_institution_read_comes_with_membership(world):
    teacher = factories.member(world.a, role="teacher")
    assert has_perm(teacher, world.a, "institution.read")
    assert not has_perm(teacher, world.a, "membership.read")
    assert not has_perm(teacher, world.b, "institution.read")


def test_campus_scope_covers_its_departments_only(world):
    main, city, city_dept, sci, _, _ = org(world.a)
    boss = factories.member(world.a, role="campus_admin", scope=city)
    assert has_perm(boss, world.a, "membership.assign", ("campus", city.id))
    assert has_perm(boss, world.a, "membership.assign", ("department", city_dept.id))
    assert not has_perm(boss, world.a, "membership.assign", ("campus", main.id))
    assert not has_perm(boss, world.a, "membership.assign", ("department", sci.id))
    assert not has_perm(boss, world.a, "membership.assign", WHOLE)


def test_department_scope_covers_descendants(world):
    main, _, _, sci, phy, lang = org(world.a)
    head = factories.member(world.a, role="head_of_department", scope=sci)
    assert has_perm(head, world.a, "membership.read", ("department", phy.id))
    assert has_perm(head, world.a, "membership.read", ("department", sci.id))
    assert not has_perm(head, world.a, "membership.read", ("department", lang.id))
    assert not has_perm(head, world.a, "membership.read", ("campus", main.id))


def test_ended_future_and_expired_assignments_grant_nothing(world):
    today = timezone.localdate()
    ended = factories.member(world.a, role="principal")
    RoleAssignment.objects.filter(membership__user=ended).update(status="ended")
    future = factories.member(world.a, role="principal", starts_on=today + dt.timedelta(days=1))
    expired = factories.member(world.a, role="principal", ends_on=today - dt.timedelta(days=1))
    last_day = factories.member(world.a, role="principal", ends_on=today)
    for person in (ended, future, expired):
        assert not has_perm(person, world.a, "membership.read")
    assert has_perm(last_day, world.a, "membership.read")


def test_today_uses_institution_time_zone(world, monkeypatch):
    utc = factories.institution(timezone="UTC")
    monkeypatch.setattr(timezone, "now", lambda: dt.datetime(2026, 10, 18, 19, 0, tzinfo=dt.UTC))
    kolkata_member = factories.member(world.a, role="principal", starts_on=dt.date(2026, 10, 19))
    utc_member = factories.member(utc, role="principal", starts_on=dt.date(2026, 10, 19))
    assert has_perm(kolkata_member, world.a, "membership.read")
    assert not has_perm(utc_member, utc, "membership.read")


def test_archived_custom_role_grants_nothing(world):
    role = factories.custom_role(world.a, permissions=["membership.read"])
    person = factories.member(world.a, custom_role=role)
    assert has_perm(person, world.a, "membership.read")
    role.is_active = False
    role.save()
    assert not has_perm(person, world.a, "membership.read")


def test_revoked_membership_or_inactive_user_grants_nothing(world):
    revoked = factories.member(world.a, role="principal")
    Membership.objects.filter(user=revoked).update(status="revoked")
    switched_off = factories.member(world.a, role="principal", is_active=False)
    assert not has_perm(revoked, world.a, "membership.read")
    assert not has_perm(revoked, world.a, "institution.read")
    assert not has_perm(switched_off, world.a, "membership.read")


def test_can_assign_is_the_grant_ceiling(world):
    main, city, *_ = org(world.a)
    boss = factories.member(world.a, role="campus_admin", scope=city)
    teacher = BUILTIN_ROLES["teacher"].permissions
    assert can_assign(boss, world.a, teacher, ("campus", city.id))
    assert not can_assign(boss, world.a, teacher, ("campus", main.id))
    assert not can_assign(boss, world.a, BUILTIN_ROLES["institution_admin"].permissions, ("campus", city.id))
    assert not can_assign(boss, world.a, frozenset({"role.manage"}), ("campus", city.id))
    assert can_assign(world.a_admin, world.a, BUILTIN_ROLES["institution_admin"].permissions, WHOLE)


def test_can_manage_person(world):
    main, city, city_dept, sci, *_ = org(world.a)
    boss = factories.member(world.a, role="campus_admin", scope=city)
    city_teacher = factories.member(world.a, role="teacher", scope=city_dept)
    split_teacher = factories.member(world.a, role="teacher", scope=city)
    factories.assign(membership_of(split_teacher, world.a), "teacher", sci)
    principal = factories.member(world.a, role="principal")
    no_role = factories.member(world.a, role=None)
    assert can_manage_person(boss, membership_of(city_teacher, world.a))
    assert not can_manage_person(boss, membership_of(split_teacher, world.a))
    assert not can_manage_person(boss, membership_of(principal, world.a))
    assert not can_manage_person(boss, membership_of(boss, world.a))
    assert not can_manage_person(boss, membership_of(no_role, world.a))
    assert can_manage_person(world.a_admin, membership_of(no_role, world.a))


def test_me_lists_roles_permissions_and_restriction(world):
    _, city, *_ = org(world.a)
    factories.member(world.a, role="campus_admin", scope=city, username="aster.campus")
    client = host(world.a.slug)
    membership = login(client, "aster.campus").json()["user"]["membership"]
    assert membership == {
        "roles": [{"label": "Campus Admin", "scope_label": "City campus"}],
        "permissions": ["institution.read", "membership.assign", "membership.read"],
        "restricted": False,
        "status_reason": "",
    }


def test_covers_ends_even_if_departments_loop(world):
    """Two parent changes at once could once loop departments; the scope walk must still finish (final review #2)."""
    import signal

    from accounts.permissions import covers
    from organization.models import Department

    a = factories.department(world.a, code="A")
    b = factories.department(world.a, code="B", parent=a)
    other = factories.department(world.a, code="C")
    Department.objects.filter(pk=a.pk).update(parent=b)

    def too_slow(*_):
        raise TimeoutError("covers() did not finish")

    signal.signal(signal.SIGALRM, too_slow)
    signal.alarm(2)
    try:
        assert not covers(world.a, ("department", other.id), ("department", a.id))
    finally:
        signal.alarm(0)
