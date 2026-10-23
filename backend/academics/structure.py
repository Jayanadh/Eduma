"""Years, terms, grades and subjects (slice 5a S5A-01, S5A-02): institution-wide, changed only with
academic_structure.manage for the whole institution."""

from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import AcademicYear, Term
from accounts.permissions import WHOLE, has_perm
from common import audit
from common.exceptions import Problem

MANAGE = "academic_structure.manage"
# Years only move forward: planned → current → closed (or planned → closed).
FORWARD = {("planned", "current"), ("current", "closed"), ("planned", "closed")}


def require_whole(actor, institution) -> None:
    if not has_perm(actor, institution, MANAGE, WHOLE):
        raise PermissionDenied("Only someone who sets up academics for the whole institution can change this.")


def _check_dates(starts_on, ends_on) -> None:
    if ends_on <= starts_on:
        raise ValidationError({"ends_on": ["End after the start."]})


def save_year(actor, institution, year: AcademicYear | None, data: dict, version: int | None = None) -> AcademicYear:
    require_whole(actor, institution)
    with transaction.atomic():
        if year is not None:
            year = AcademicYear.objects.select_for_update().get(pk=year.pk)
            year.check_version(version)
            wanted = data.get("status", year.status)
            if wanted != year.status and (year.status, wanted) not in FORWARD:
                raise Problem(
                    409, "invalid_transition", f"A {year.get_status_display().lower()} year can't become {wanted}."
                )
        else:
            year = AcademicYear(institution=institution)
        for name in ("code", "starts_on", "ends_on", "status"):
            if name in data:
                setattr(year, name, data[name])
        _check_dates(year.starts_on, year.ends_on)
        others = institution.academic_years.exclude(pk=year.pk)
        if clash := others.filter(starts_on__lte=year.ends_on, ends_on__gte=year.starts_on).first():
            raise ValidationError({"starts_on": [f"This overlaps {clash.code}."]})
        if others.filter(code=year.code).exists():
            raise ValidationError({"code": ["Another academic year has this name."]})
        if year.pk and year.terms.filter(starts_on__lt=year.starts_on).exists():
            raise ValidationError({"starts_on": ["A term would start before the year."]})
        if year.pk and year.terms.filter(ends_on__gt=year.ends_on).exists():
            raise ValidationError({"ends_on": ["A term would end after the year."]})
        if year.status == AcademicYear.Status.CURRENT and others.filter(status=AcademicYear.Status.CURRENT).exists():
            raise Problem(409, "another_current_year", "Close the current academic year before making another current.")
        year.save()
        audit.log(actor, "academic_year.saved", year, f"Academic year {year.code} saved", institution=institution)
        return year


def delete_year(actor, year: AcademicYear) -> None:
    require_whole(actor, year.institution)
    if year.status != AcademicYear.Status.PLANNED or year.sections.exists():
        raise Problem(409, "in_use", "Only a planned year without sections can be removed; close it instead.")
    audit.log(actor, "academic_year.deleted", year, f"Academic year {year.code} removed", institution=year.institution)
    year.delete()


def save_term(actor, year: AcademicYear, term: Term | None, data: dict) -> Term:
    require_whole(actor, year.institution)
    with transaction.atomic():
        AcademicYear.objects.select_for_update().get(pk=year.pk)
        term = term or Term(year=year)
        for name in ("name", "ordinal", "starts_on", "ends_on"):
            if name in data:
                setattr(term, name, data[name])
        _check_dates(term.starts_on, term.ends_on)
        if term.starts_on < year.starts_on:
            raise ValidationError({"starts_on": ["The term must start inside the year."]})
        if term.ends_on > year.ends_on:
            raise ValidationError({"ends_on": ["The term must end inside the year."]})
        others = year.terms.exclude(pk=term.pk)
        if clash := others.filter(starts_on__lte=term.ends_on, ends_on__gte=term.starts_on).first():
            raise ValidationError({"starts_on": [f"This overlaps {clash.name}."]})
        if others.filter(ordinal=term.ordinal).exists():
            raise ValidationError({"ordinal": ["Another term has this number."]})
        term.save()
        return term


def save_named(actor, institution, model, row, data: dict, version: int | None = None):
    """Create or change a grade or subject; codes are unique per institution."""
    require_whole(actor, institution)
    with transaction.atomic():
        if row is not None:
            row = model.objects.select_for_update().get(pk=row.pk)
            row.check_version(version)
        else:
            row = model(institution=institution)
        for name, value in data.items():
            setattr(row, name, value)
        if model.objects.filter(institution=institution, code=row.code).exclude(pk=row.pk).exists():
            raise ValidationError({"code": ["Another one here has this code."]})
        try:
            with transaction.atomic():
                row.save()
        except IntegrityError as error:
            raise ValidationError({"code": ["Another one here has this code."]}) from error
        audit.log(actor, f"{model._meta.model_name}.saved", row, f"{row.name} saved", institution=institution)
        return row
