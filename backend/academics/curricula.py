"""Curriculum versions — the regulation a cohort follows (slice 5b S5B-02, S5B-04). Only a draft changes; a published
one is frozen and a change to it is a new revision. Managed like the program they belong to."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics import programs
from academics.models import CurriculumCourse, CurriculumVersion, Program
from common import audit
from common.exceptions import Problem


def _require(actor, program: Program) -> None:
    if not programs.can_manage(actor, program):
        raise PermissionDenied("Your role does not cover this program's department.")


def _locked(curriculum: CurriculumVersion) -> CurriculumVersion:
    return (
        CurriculumVersion.objects.select_for_update(of=("self",))
        .select_related("program__institution")
        .get(pk=curriculum.pk)
    )


def _draft(actor, curriculum: CurriculumVersion) -> CurriculumVersion:
    """Lock a draft for a change, refusing anything else (409 published / retired)."""
    curriculum = _locked(curriculum)
    _require(actor, curriculum.program)
    if curriculum.status != CurriculumVersion.Status.DRAFT:
        raise Problem(
            409,
            curriculum.status,
            f"{curriculum} is {curriculum.status}; draft a new revision to change it.",
        )
    return curriculum


def _log(actor, action: str, curriculum: CurriculumVersion, what: str) -> None:
    program = curriculum.program
    summary = f"{program.code} {curriculum} {what}"
    audit.log(actor, f"curriculum.{action}", curriculum, summary, institution=program.institution)


def create(actor, program: Program, data: dict) -> CurriculumVersion:
    _require(actor, program)
    with transaction.atomic():
        Program.objects.select_for_update().get(pk=program.pk)
        if program.curricula.filter(regulation=data["regulation"]).exists():
            raise ValidationError({"regulation": ["This program already has this regulation; revise it instead."]})
        curriculum = CurriculumVersion.objects.create(program=program, revision=1, **data)
        _log(actor, "drafted", curriculum, "drafted")
        return curriculum


def save(actor, curriculum: CurriculumVersion, data: dict, version: int) -> CurriculumVersion:
    with transaction.atomic():
        curriculum = _draft(actor, curriculum)
        curriculum.check_version(version)
        for name in ("cohort", "credits_required"):
            if name in data:
                setattr(curriculum, name, data[name])
        curriculum.save()
        return curriculum


def _prerequisites(curriculum: CurriculumVersion, course_id, wanted: list) -> list:
    """The prerequisites as course ids, refusing ones outside the curriculum, the course itself, or a loop."""
    edges: dict = {}
    for cc_course, prerequisite in CurriculumCourse.prerequisites.through.objects.filter(
        curriculumcourse__curriculum=curriculum
    ).values_list("curriculumcourse__course_id", "course_id"):
        edges.setdefault(cc_course, set()).add(prerequisite)
    present = set(curriculum.courses.values_list("course_id", flat=True))
    wanted = set(wanted)
    if course_id in wanted:
        raise ValidationError({"prerequisites": ["A course can't require itself."]})
    if wanted - present:
        raise ValidationError({"prerequisites": ["Add a prerequisite to this curriculum first."]})
    # A loop exists if anything the course would require already requires it, however indirectly.
    edges[course_id] = wanted
    todo, seen = list(wanted), set()
    while todo:
        node = todo.pop()
        if node == course_id:
            raise ValidationError({"prerequisites": ["These prerequisites would make a loop."]})
        if node not in seen:
            seen.add(node)
            todo.extend(edges.get(node, ()))
    return list(wanted)


def _term(curriculum: CurriculumVersion, term: int) -> None:
    if not 1 <= term <= curriculum.program.length_terms:
        raise ValidationError({"term": [f"Choose a term from 1 to {curriculum.program.length_terms}."]})


def add_course(actor, curriculum: CurriculumVersion, data: dict) -> CurriculumVersion:
    with transaction.atomic():
        curriculum = _draft(actor, curriculum)
        course = curriculum.program.institution.courses.filter(pk=data["course"], is_active=True).first()
        if course is None:
            raise ValidationError({"course": ["Choose an active course."]})
        if curriculum.courses.filter(course=course).exists():
            raise ValidationError({"course": ["This course is already in the curriculum."]})
        _term(curriculum, data["term"])
        prerequisites = _prerequisites(curriculum, course.id, data.get("prerequisites", []))
        entry = CurriculumCourse.objects.create(
            curriculum=curriculum,
            course=course,
            category=data["category"],
            term=data["term"],
            elective_group=data.get("elective_group", ""),
        )
        entry.prerequisites.set(prerequisites)
        curriculum.save()  # a new version: publishing must be of what was seen
        _log(actor, "course_added", curriculum, f"gained {course.code}")
        return curriculum


def change_course(actor, curriculum: CurriculumVersion, entry: CurriculumCourse, data: dict) -> CurriculumVersion:
    with transaction.atomic():
        curriculum = _draft(actor, curriculum)
        if "term" in data:
            _term(curriculum, data["term"])
        for name in ("category", "term", "elective_group"):
            if name in data:
                setattr(entry, name, data[name])
        entry.save()
        if "prerequisites" in data:
            entry.prerequisites.set(_prerequisites(curriculum, entry.course_id, data["prerequisites"]))
        curriculum.save()
        _log(actor, "course_changed", curriculum, f"changed {entry.course.code}")
        return curriculum


def remove_course(actor, curriculum: CurriculumVersion, entry: CurriculumCourse) -> CurriculumVersion:
    with transaction.atomic():
        curriculum = _draft(actor, curriculum)
        if needed := curriculum.courses.filter(prerequisites=entry.course).select_related("course").first():
            raise Problem(409, "in_use", f"{needed.course.code} requires {entry.course.code}; change that first.")
        entry.delete()
        curriculum.save()
        _log(actor, "course_removed", curriculum, f"lost {entry.course.code}")
        return curriculum


def publish(actor, curriculum: CurriculumVersion, version: int) -> CurriculumVersion:
    with transaction.atomic():
        curriculum = _locked(curriculum)
        _require(actor, curriculum.program)
        curriculum.check_version(version)
        if curriculum.status != CurriculumVersion.Status.DRAFT:
            raise Problem(409, "invalid_transition", f"{curriculum} is already {curriculum.status}.")
        if not curriculum.courses.exists():
            raise ValidationError({"courses": ["Add at least one course before publishing."]})
        curriculum.status = CurriculumVersion.Status.PUBLISHED
        curriculum.published_by, curriculum.published_at = actor, timezone.now()
        curriculum.save()
        _log(actor, "published", curriculum, "published")
        return curriculum


def retire(actor, curriculum: CurriculumVersion, version: int) -> CurriculumVersion:
    with transaction.atomic():
        curriculum = _locked(curriculum)
        _require(actor, curriculum.program)
        curriculum.check_version(version)
        if curriculum.status != CurriculumVersion.Status.PUBLISHED:
            raise Problem(409, "invalid_transition", f"Only a published regulation can be retired; {curriculum} isn't.")
        curriculum.status = CurriculumVersion.Status.RETIRED
        curriculum.save()
        _log(actor, "retired", curriculum, "retired")
        return curriculum


def revise(actor, curriculum: CurriculumVersion, version: int) -> CurriculumVersion:
    """A draft copy of a published regulation as its next revision; the published one stays as it is."""
    with transaction.atomic():
        source = _locked(curriculum)
        _require(actor, source.program)
        source.check_version(version)
        if source.status != CurriculumVersion.Status.PUBLISHED:
            raise Problem(409, "invalid_transition", "Only a published regulation can be revised; edit this draft.")
        Program.objects.select_for_update().get(pk=source.program_id)  # one revision number at a time
        latest = source.program.curricula.filter(regulation=source.regulation).aggregate(n=Max("revision"))["n"]
        draft = CurriculumVersion.objects.create(
            program=source.program,
            regulation=source.regulation,
            revision=latest + 1,
            cohort=source.cohort,
            credits_required=source.credits_required,
        )
        for entry in source.courses.prefetch_related("prerequisites"):
            prerequisites = list(entry.prerequisites.all())
            entry.pk, entry.curriculum = None, draft
            entry._state.adding = True
            entry.save()
            entry.prerequisites.set(prerequisites)
        _log(actor, "revised", draft, f"drafted from revision {source.revision}")
        return draft


def for_cohort(program: Program, entry_year: int) -> CurriculumVersion | None:
    """The regulation a cohort entering in `entry_year` follows: published, from that year or before, the latest."""
    published = program.curricula.filter(status=CurriculumVersion.Status.PUBLISHED, cohort__lte=entry_year)
    return published.order_by("-cohort", "-revision", "-published_at").first()


def summary_item(curriculum: CurriculumVersion) -> dict:
    return {
        "id": str(curriculum.id),
        "version": curriculum.version,
        "regulation": curriculum.regulation,
        "revision": curriculum.revision,
        "cohort": curriculum.cohort,
        "credits_required": str(curriculum.credits_required),
        "status": curriculum.status,
        "status_label": curriculum.get_status_display(),
        "published_at": curriculum.published_at,
    }


def curriculum_item(curriculum: CurriculumVersion, viewer) -> dict:
    program = curriculum.program
    entries = curriculum.courses.select_related("course").prefetch_related("prerequisites")
    terms: dict = {}
    total = Decimal(0)
    for entry in entries:
        total += entry.course.credits
        terms.setdefault(entry.term, []).append(
            {
                "id": str(entry.id),
                "course": {
                    "id": str(entry.course_id),
                    "code": entry.course.code,
                    "title": entry.course.title,
                    "credits": str(entry.course.credits),
                    "kind": entry.course.kind,
                },
                "category": entry.category,
                "category_label": entry.get_category_display(),
                "term": entry.term,
                "elective_group": entry.elective_group,
                "prerequisites": sorted(p.code for p in entry.prerequisites.all()),
            }
        )
    return {
        **summary_item(curriculum),
        "program": {
            "id": str(program.id),
            "code": program.code,
            "name": program.name,
            "length_terms": program.length_terms,
        },
        "total_credits": str(total),
        "terms": [{"term": term, "courses": rows} for term, rows in sorted(terms.items())],
        "can_manage": programs.can_manage(viewer, program),
    }
