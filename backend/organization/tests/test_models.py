import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from organization.models import validate_code
from testing import factories


def test_code_is_upper_cased_and_checked():
    assert validate_code(" sci-1 ") == "SCI-1"
    for bad in ("x", "a b", "-AB"):
        with pytest.raises(ValidationError):
            validate_code(bad)


def test_codes_unique_per_institution_not_globally(world):
    factories.campus(world.a, code="CITY")
    factories.campus(world.b, code="CITY")
    with pytest.raises(IntegrityError):
        factories.campus(world.a, code="CITY")


def test_descendants_cover_all_levels(world):
    sci = factories.department(world.a, code="SCI")
    phy = factories.department(world.a, code="PHY", parent=sci)
    lab = factories.department(world.a, code="LAB", parent=phy)
    factories.department(world.a, code="LANG")
    assert sci.descendant_ids() == {phy.id, lab.id}
    assert lab.descendant_ids() == set()
