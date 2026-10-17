"""Builders for tests. Each makes a valid record with sensible defaults; pass keywords to change any of them."""
import itertools

from accounts.models import Membership, Role, User
from institutions.models import Category, Institution, LifecycleStatus

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


def member(institution_: Institution, role: str = Role.INSTITUTION_ADMIN, **kw) -> User:
    person = user(**kw)
    Membership.objects.create(institution=institution_, user=person, role=role)
    return person
