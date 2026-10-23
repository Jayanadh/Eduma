"""Higher-education structure models (slice 5b §3)."""

import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from academics.models import (
    AcademicYear,
    Course,
    CourseOffering,
    CurriculumCourse,
    CurriculumVersion,
    GradeLevel,
    Program,
    Section,
    TeachingAssignment,
    Term,
)
from accounts.models import Membership
from testing import factories


def refused(make):
    with pytest.raises(IntegrityError), transaction.atomic():
        make()


@pytest.fixture
def college(world):
    year = AcademicYear.objects.create(
        institution=world.a, code="2026–27", starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2027, 3, 31)
    )
    term = Term.objects.create(
        year=year, name="Semester 1", ordinal=1, starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2026, 11, 30)
    )
    program = Program.objects.create(
        institution=world.a, code="BSC-PHY", name="B.Sc Physics", qualification="B.Sc", length_terms=6
    )
    course = Course.objects.create(institution=world.a, code="PHY101", title="Mechanics", credits=4, kind="theory")
    campus = factories.campus(world.a, code="MAIN", name="Main campus")
    return year, term, program, course, campus


def test_codes_unique_per_institution(world, college):
    _, _, program, course, _ = college
    refused(
        lambda: Program.objects.create(
            institution=world.a, code="BSC-PHY", name="Again", qualification="B.Sc", length_terms=6
        )
    )
    refused(lambda: Course.objects.create(institution=world.a, code="PHY101", title="Again", credits=4, kind="theory"))
    Program.objects.create(institution=world.b, code="BSC-PHY", name="Elsewhere", qualification="B.Sc", length_terms=6)


def test_a_course_once_per_curriculum_and_offering_codes_per_term(world, college):
    _, term, program, course, campus = college
    curriculum = CurriculumVersion.objects.create(
        program=program, regulation="R2026", revision=1, cohort=2026, credits_required=120
    )
    CurriculumCourse.objects.create(curriculum=curriculum, course=course, category="core", term=1)
    refused(lambda: CurriculumCourse.objects.create(curriculum=curriculum, course=course, category="core", term=2))
    CourseOffering.objects.create(institution=world.a, course=course, term=term, campus=campus, code="A", capacity=60)
    refused(
        lambda: CourseOffering.objects.create(
            institution=world.a, course=course, term=term, campus=campus, code="A", capacity=60
        )
    )


def test_a_section_names_a_grade_or_a_program(world, college):
    year, _, program, _, campus = college
    grade = GradeLevel.objects.create(institution=world.a, code="C6", name="Class 6")
    Section.objects.create(
        institution=world.a, year=year, program=program, campus=campus, code="BSC-PHY 2026 A", capacity=60
    )
    refused(
        lambda: Section.objects.create(
            institution=world.a, year=year, grade=grade, program=program, campus=campus, code="X", capacity=1
        )
    )
    refused(lambda: Section.objects.create(institution=world.a, year=year, campus=campus, code="Y", capacity=1))


def test_a_teaching_assignment_names_one_target(world, college):
    year, term, program, course, campus = college
    section = Section.objects.create(
        institution=world.a, year=year, program=program, campus=campus, code="B", capacity=60
    )
    offering = CourseOffering.objects.create(
        institution=world.a, course=course, term=term, campus=campus, code="A", capacity=60
    )
    membership = Membership.objects.get(user=world.a_admin)

    def assign(**target):
        return TeachingAssignment.objects.create(
            membership=membership, starts_on=dt.date(2026, 6, 1), created_by=world.a_admin, **target
        )

    assign(section=section)
    assign(offering=offering)
    refused(lambda: assign(section=section, offering=offering))
    refused(lambda: assign())
