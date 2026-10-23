import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from academics.models import AcademicYear, EnrollmentPeriod, GradeLevel, Section
from accounts.roles import BUILTIN_ROLES, PERMISSIONS
from institutions.modules import MODULES
from students.models import Enrollment, Person, Student
from testing import factories


def year(institution, code="2026–27", start=dt.date(2026, 6, 1), end=dt.date(2027, 3, 31)):
    return AcademicYear.objects.create(institution=institution, code=code, starts_on=start, ends_on=end)


def test_codes_are_unique_where_they_must_be(world):
    first = year(world.a)
    year(world.b)
    with pytest.raises(IntegrityError), transaction.atomic():
        year(world.a)
    grade = GradeLevel.objects.create(institution=world.a, code="C6", name="Class 6", order=6)
    main = factories.campus(world.a, code="MAIN", name="Main campus")
    Section.objects.create(institution=world.a, year=first, grade=grade, campus=main, code="6A", capacity=40)
    with pytest.raises(IntegrityError), transaction.atomic():
        Section.objects.create(institution=world.a, year=first, grade=grade, campus=main, code="6A", capacity=40)


def test_one_placement_per_enrollment_and_year(world):
    first = year(world.a)
    grade = GradeLevel.objects.create(institution=world.a, code="C6", name="Class 6", order=6)
    main = factories.campus(world.a, code="MAIN", name="Main campus")
    section = Section.objects.create(institution=world.a, year=first, grade=grade, campus=main, code="6A", capacity=40)
    person = Person.objects.create(institution=world.a, full_name="Arjun")
    student = Student.objects.create(
        institution=world.a, person=person, number="2026-0001", admitted_on=dt.date(2026, 6, 1)
    )
    enrollment = Enrollment.objects.create(
        student=student, institution=world.a, academic_year="2026–27", place_code="C6", place_label="Class 6",
        entry_date=dt.date(2026, 6, 1),
    )  # fmt: skip

    def place():
        return EnrollmentPeriod.objects.create(
            enrollment=enrollment, institution=world.a, year=first, section=section, grade=grade, campus=main
        )

    place()
    with pytest.raises(IntegrityError), transaction.atomic():
        place()


def test_permission_and_module():
    assert "academic_structure.manage" in BUILTIN_ROLES["registrar"].permissions
    assert PERMISSIONS["academic_structure.manage"].institution_only is False
    assert MODULES["academics"].available is True
