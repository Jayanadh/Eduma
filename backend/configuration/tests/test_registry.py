import datetime as dt

import pytest
from django.core.exceptions import ValidationError

from accounts.permissions import today_for
from accounts.roles import BUILTIN_ROLES
from configuration.models import SettingRevision
from configuration.registry import DEFINITIONS, academic_year, setting
from testing import factories


def published(institution, key, value, effective_from, status="published", number=None):
    return SettingRevision.objects.create(
        institution=institution,
        key=key,
        number=number or SettingRevision.objects.filter(institution=institution, key=key).count() + 1,
        value=value,
        status=status,
        effective_from=effective_from,
        reason="test",
    )


def test_defaults_follow_category(world):
    assert setting(world.a, "academic.year_start") == 6
    assert setting(world.b, "academic.year_start") == 7
    assert setting(world.a, "access.role_approval") is False
    assert setting(world.a, "modules.enabled") == []


def test_value_in_force_follows_effective_dates(world):
    today = today_for(world.a)
    published(world.a, "academic.year_start", 4, today)
    published(world.a, "academic.year_start", 1, today + dt.timedelta(days=10))
    published(world.a, "academic.year_start", 9, today, status="superseded")
    assert setting(world.a, "academic.year_start") == 4
    assert setting(world.a, "academic.year_start", on=today + dt.timedelta(days=10)) == 1


def test_enabled_modules_are_cut_to_the_plan(world):
    world.a.modules = ["students"]
    world.a.save()
    published(world.a, "modules.enabled", ["students", "fees"], today_for(world.a))
    assert setting(world.a, "modules.enabled") == ["students"]


def test_clean_rules(world):
    world.a.modules = ["students", "fees"]
    world.a.save()
    modules = DEFINITIONS["modules.enabled"].clean
    with pytest.raises(ValidationError, match="Library is not in this institution's plan."):
        modules(world.a, ["library"])
    with pytest.raises(ValidationError, match="Fees needs Students and guardians switched on."):
        modules(world.a, ["fees"])
    assert modules(world.a, ["students", "fees", "students"]) == ["fees", "students"]
    with pytest.raises(ValidationError):
        DEFINITIONS["academic.year_start"].clean(world.a, 13)
    approval = DEFINITIONS["access.role_approval"].clean
    with pytest.raises(ValidationError, match="Turning this on needs at least two people"):
        approval(world.a, True)
    factories.member(world.a, role="institution_admin")
    assert approval(world.a, True) is True
    assert approval(world.a, False) is False


def test_descriptions_and_previews(world):
    year = DEFINITIONS["academic.year_start"]
    assert year.describe(world.a, 4) == "Starts in April"
    assert year.preview(world.a, 6, 4, dt.date(2027, 4, 1)) == ["The 2027–28 year runs 1 Apr 2027 – 31 Mar 2028."]
    world.a.modules = ["students", "fees"]
    modules = DEFINITIONS["modules.enabled"]
    assert modules.preview(world.a, ["students"], ["fees", "students"], dt.date(2027, 4, 1)) == ["Switches on: Fees"]
    assert modules.preview(world.a, ["fees", "students"], ["students"], dt.date(2027, 4, 1)) == ["Switches off: Fees"]
    approval = DEFINITIONS["access.role_approval"]
    assert approval.preview(world.a, False, True, dt.date(2027, 4, 1)) == [
        "From 1 Apr 2027, giving powerful roles (any that can change the institution or its staff) waits for a second "
        "person's approval."
    ]
    assert academic_year(6, dt.date(2027, 3, 31)) == ("2026–27", dt.date(2026, 6, 1), dt.date(2027, 5, 31))


def test_admin_gets_configuration_permissions():
    assert {"configuration.edit", "configuration.publish"} <= BUILTIN_ROLES["institution_admin"].permissions
