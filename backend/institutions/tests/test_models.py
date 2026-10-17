import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from common import audit
from institutions.models import validate_slug
from testing import factories


@pytest.mark.parametrize(
    "raw,ok",
    [("aster-school", True), ("WWW", False), ("-ab", False), ("ab-", False), ("ab", False), ("Aster", True),
     ("a" * 40, True), ("a" * 41, False), ("api", False), ("a_b", False), ("sri-vidya-2", True)],
)
def test_validate_slug(raw, ok):
    if ok:
        assert validate_slug(raw) == raw.lower()
    else:
        with pytest.raises(ValidationError):
            validate_slug(raw)


def test_reserved_message():
    with pytest.raises(ValidationError, match="This address is reserved."):
        validate_slug("Console")


def test_udise_unique_only_when_present(db):
    factories.institution(udise_code="")
    factories.institution(udise_code="")
    factories.institution(udise_code="28123456789")
    with pytest.raises(IntegrityError):
        factories.institution(udise_code="28123456789")


def test_audit_log_infers_institution(world):
    event = audit.log(world.platform_admin, "institution.updated", world.a, "Updated")
    assert event.institution_id == world.a.id
    assert event.actor_id == world.platform_admin.id
    member_event = audit.log(world.a_admin, "membership.password_reset", world.a_admin.memberships.get(), "Reset")
    assert member_event.institution_id == world.a.id
