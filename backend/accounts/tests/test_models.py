import pytest
from django.core.exceptions import ValidationError

from accounts.models import Membership, validate_username
from accounts.permissions import active_membership, has_perm
from common.exceptions import VersionConflict
from testing import factories


def test_username_is_lowercased_and_validated(db):
    person = factories.user(username="  Aster.Admin ")
    assert person.username == "aster.admin"
    assert validate_username(" Aster.Admin ") == "aster.admin"
    with pytest.raises(ValidationError):
        validate_username("ab")
    with pytest.raises(ValidationError):
        validate_username("has space")


def test_has_perm_needs_active_membership_in_that_institution(world):
    assert has_perm(world.a_admin, world.a, "institution_brand.update")
    assert not has_perm(world.a_admin, world.b, "institution_brand.update")
    assert not has_perm(world.a_admin, world.a, "institution.create")
    Membership.objects.filter(user=world.a_admin).update(status="revoked")
    assert active_membership(world.a_admin, world.a) is None
    assert not has_perm(world.a_admin, world.a, "institution_brand.update")


def test_switched_off_user_has_no_permissions(world):
    world.a_admin.is_active = False
    world.a_admin.save()
    assert not has_perm(world.a_admin, world.a, "institution.read")


def test_version_increments_and_check_version_raises(world):
    world.a.display_name = "New"
    world.a.save()
    assert world.a.version == 2
    world.a.check_version(2)
    with pytest.raises(VersionConflict):
        world.a.check_version(1)
    with pytest.raises(VersionConflict):
        world.a.check_version(None)
