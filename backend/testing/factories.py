"""Builders for tests. Each makes a valid record with sensible defaults; pass keywords to change any of them."""

import itertools

from accounts.models import CustomRole, Membership, RoleAssignment, User
from accounts.permissions import today_for
from institutions.models import Category, Institution, LifecycleStatus
from organization.models import Campus, Department

PASSWORD = "Test-pass-2026"
_n = itertools.count(1)


def user(password: str = PASSWORD, **kw) -> User:
    n = next(_n)
    person = User(**{"username": f"user{n}", "full_name": f"User {n}", **kw})
    person.set_password(password)
    person.save()
    return person


def platform_admin(**kw) -> User:
    return user(**{"is_platform_admin": True, **kw})


def institution(**kw) -> Institution:
    n = next(_n)
    return Institution.objects.create(
        **{
            "slug": f"inst{n}",
            "legal_name": f"Institution {n} Trust",
            "display_name": f"Institution {n}",
            "category": Category.SCHOOL,
            "lifecycle_status": LifecycleStatus.ACTIVE,
            "contact_email": f"office{n}@example.com",
            "contact_phone": "+91 90000 00000",
            **kw,
        }
    )


def member(
    institution_: Institution,
    role: str | None = "institution_admin",
    scope=None,
    *,
    custom_role: CustomRole | None = None,
    starts_on=None,
    ends_on=None,
    **kw,
) -> User:
    """A login in the institution with one role (none if role and custom_role are None). scope: None for the whole
    institution, or a Campus or Department."""
    person = user(**kw)
    membership = Membership.objects.create(institution=institution_, user=person)
    if role is not None or custom_role is not None:
        assign(membership, role, scope, custom_role=custom_role, starts_on=starts_on, ends_on=ends_on)
    return person


def assign(
    membership: Membership, role: str | None = "teacher", scope=None, *, custom_role=None, starts_on=None, ends_on=None
) -> RoleAssignment:
    kind = "institution" if scope is None else "campus" if isinstance(scope, Campus) else "department"
    return RoleAssignment.objects.create(
        membership=membership,
        institution_id=membership.institution_id,
        role_key="" if custom_role is not None else role,
        custom_role=custom_role,
        scope_type=kind,
        campus=scope if kind == "campus" else None,
        department=scope if kind == "department" else None,
        starts_on=starts_on or today_for(membership.institution),
        ends_on=ends_on,
    )


def custom_role(institution_: Institution, permissions=(), **kw) -> CustomRole:
    n = next(_n)
    return CustomRole.objects.create(
        **{"institution": institution_, "name": f"Role {n}", "permissions": sorted(permissions), **kw}
    )


def campus(institution_: Institution, **kw) -> Campus:
    n = next(_n)
    return Campus.objects.create(**{"institution": institution_, "code": f"C{n}", "name": f"Campus {n}", **kw})


def department(institution_: Institution, **kw) -> Department:
    n = next(_n)
    if kw.get("parent") is not None:
        kw.setdefault("campus", kw["parent"].campus)
    return Department.objects.create(**{"institution": institution_, "code": f"D{n}", "name": f"Department {n}", **kw})
