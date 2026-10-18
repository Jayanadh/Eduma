"""The settings an institution can change (slice 3 spec §4). Each is typed and checked here; only settings something
reads are registered, and later slices add their own."""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.http import Http404

from institutions.modules import MODULES

MONTHS = [dt.date(2000, m, 1).strftime("%B") for m in range(1, 13)]


def day(value: dt.date) -> str:
    """1 Apr 2027."""
    return f"{value.day} {value:%b} {value.year}"


@dataclass(frozen=True)
class Definition:
    key: str
    label: str
    help: str
    kind: str  # "modules", "bool" or "month"
    default: Callable[[Any], Any]
    needs_approval: bool
    clean: Callable[[Any, Any], Any]
    describe: Callable[[Any, Any], str]
    preview: Callable[[Any, Any, Any, dt.date], list[str]]


def academic_year(month: int, on: dt.date) -> tuple[str, dt.date, dt.date]:
    """The academic year containing `on` for a year starting in `month`: ("2026–27", start, end)."""
    first = on.year if on.month >= month else on.year - 1
    start = dt.date(first, month, 1)
    end = dt.date(first + 1, month, 1) - dt.timedelta(days=1)
    label = f"{first}–{str(first + 1)[-2:]}" if month != 1 else str(first)
    return label, start, end


def _labels(keys) -> str:
    return ", ".join(MODULES[key].label for key in keys if key in MODULES)


def _clean_modules(institution, value) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(key, str) for key in value):
        raise ValidationError("Choose modules from the list.")
    chosen = sorted(set(value))
    for key in chosen:
        if key not in institution.modules:
            label = MODULES[key].label if key in MODULES else key
            raise ValidationError(f"{label} is not in this institution's plan.")
    for key in chosen:
        for needed in MODULES[key].depends_on:
            if needed not in chosen:
                raise ValidationError(f"{MODULES[key].label} needs {MODULES[needed].label} switched on.")
    return chosen


def _preview_modules(institution, old, new, effective_from) -> list[str]:
    lines = []
    if on := sorted(set(new) - set(old)):
        lines.append(f"Switches on: {_labels(on)}")
    if off := sorted(set(old) - set(new)):
        lines.append(f"Switches off: {_labels(off)}")
    return lines


def _whole_institution_assigners(institution) -> int:
    from accounts.permissions import has_perm

    members = institution.memberships.filter(status="active", user__is_active=True).select_related("user")
    return sum(1 for membership in members if has_perm(membership.user, institution, "membership.assign"))


def _clean_approval(institution, value) -> bool:
    if not isinstance(value, bool):
        raise ValidationError("Choose on or off.")
    if value and _whole_institution_assigners(institution) < 2:
        raise ValidationError(
            "Turning this on needs at least two people who can add staff for the whole institution, so one can "
            "approve the other's requests."
        )
    return value


def _preview_approval(institution, old, new, effective_from) -> list[str]:
    if new and not old:
        return [
            f"From {day(effective_from)}, giving powerful roles (any that can change the institution or its staff) "
            "waits for a second person's approval."
        ]
    if old and not new:
        return [
            f"From {day(effective_from)}, roles take effect when given. Requests already waiting still need a decision."
        ]
    return []


def _clean_month(institution, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 12:
        raise ValidationError("Choose a month.")
    return value


def _preview_month(institution, old, new, effective_from) -> list[str]:
    if old == new:
        return []
    label, start, end = academic_year(new, effective_from)
    return [f"The {label} year runs {day(start)} – {day(end)}."]


DEFINITIONS: dict[str, Definition] = {
    d.key: d
    for d in (
        Definition(
            "modules.enabled",
            "Modules switched on",
            "Which of the modules in your plan are in use. A module needs the ones it builds on.",
            "modules",
            lambda institution: [],
            False,
            _clean_modules,
            lambda institution, value: f"Switched on: {_labels(value)}" if value else "None switched on",
            _preview_modules,
        ),
        Definition(
            "access.role_approval",
            "Approval for powerful roles",
            "When on, a role that can change the institution or its staff waits for a second person's approval.",
            "bool",
            lambda institution: False,
            True,
            _clean_approval,
            lambda institution, value: "On: a second person approves" if value else "Off: roles take effect when given",
            _preview_approval,
        ),
        Definition(
            "academic.year_start",
            "Academic year starts",
            "The month your academic year begins. Admissions and academics use it.",
            "month",
            lambda institution: 6 if institution.category == "school" else 7,
            False,
            _clean_month,
            lambda institution, value: f"Starts in {MONTHS[value - 1]}",
            _preview_month,
        ),
    )
}


def definition(key: str) -> Definition:
    if key not in DEFINITIONS:
        raise Http404
    return DEFINITIONS[key]


def setting(institution, key: str, on: dt.date | None = None):
    """The value in force on `on` (default: the institution's today): the latest published revision that has started,
    else the default. Modules switched on are also cut to the institution's plan."""
    from accounts.permissions import today_for
    from configuration.models import SettingRevision

    found = definition(key)
    on = on or today_for(institution)
    revision = (
        SettingRevision.objects.filter(
            institution=institution, key=key, status=SettingRevision.Status.PUBLISHED, effective_from__lte=on
        )
        .order_by("-effective_from", "-number")
        .first()
    )
    value = revision.value if revision else found.default(institution)
    if key == "modules.enabled":
        value = sorted(set(value) & set(institution.modules))
    return value
