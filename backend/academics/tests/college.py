"""A small college for registration and progress tests: B.Sc Physics with regulation R2026 published, Semester 1 open
for registration, and its offerings."""

import datetime as dt
from types import SimpleNamespace

from academics.models import (
    AcademicYear,
    Course,
    CourseOffering,
    CurriculumCourse,
    CurriculumVersion,
    Program,
    RegistrationWindow,
    Term,
)
from accounts.permissions import today_for
from students.models import Enrollment, Person, Student
from testing import factories


def build(institution, **window) -> SimpleNamespace:
    today = today_for(institution)
    c = SimpleNamespace(institution=institution, today=today)
    c.campus = factories.campus(institution, code="MAIN", name="Main campus")
    c.year = AcademicYear.objects.create(
        institution=institution, code="2026–27", starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2027, 3, 31),
        status="current",
    )  # fmt: skip
    c.term = Term.objects.create(
        year=c.year, name="Semester 1", ordinal=1, starts_on=c.year.starts_on, ends_on=dt.date(2026, 10, 31)
    )
    c.program = Program.objects.create(
        institution=institution, code="BSC-PHY", name="B.Sc Physics", qualification="B.Sc", length_terms=6
    )
    c.regulation = CurriculumVersion.objects.create(
        program=c.program, regulation="R2026", revision=1, cohort=2026, credits_required=12, status="published"
    )
    c.courses = {}
    for code, credits, kind, term, needs in (
        ("PHY101", 4, "theory", 1, ()),
        ("PHY101L", 1, "lab", 1, ()),
        ("MAT101", 3, "theory", 1, ()),
        ("PHY201", 4, "theory", 3, ("PHY101",)),
    ):
        course = Course.objects.create(institution=institution, code=code, title=code, credits=credits, kind=kind)
        c.courses[code] = course
        entry = CurriculumCourse.objects.create(curriculum=c.regulation, course=course, category="core", term=term)
        entry.prerequisites.set([c.courses[n] for n in needs])
    c.outside = Course.objects.create(institution=institution, code="ART100", title="Art", credits=2, kind="theory")
    c.window = RegistrationWindow.objects.create(
        institution=institution, term=c.term, opens_on=today - dt.timedelta(days=5),
        closes_on=today + dt.timedelta(days=5), drop_until=today + dt.timedelta(days=3), **window,
    )  # fmt: skip

    def offer(code, section="A", capacity=30, linked_to=None):
        return CourseOffering.objects.create(
            institution=institution, course=c.courses.get(code) or c.outside, term=c.term, campus=c.campus,
            code=section, capacity=capacity, status="open", linked_to=linked_to,
        )  # fmt: skip

    c.offer = offer
    c.lecture = offer("PHY101", capacity=2)
    c.lab = offer("PHY101L", "A1", capacity=2, linked_to=c.lecture)
    c.maths = offer("MAT101", capacity=1)
    c.phy201 = offer("PHY201")
    c.art = offer("ART100")
    return c


def student(c, number, name="Learner", pinned=True) -> Student:
    person = Person.objects.create(institution=c.institution, full_name=name)
    found = Student.objects.create(
        institution=c.institution, person=person, number=number, admitted_on=dt.date(2026, 6, 1)
    )
    Enrollment.objects.create(
        student=found, institution=c.institution, academic_year="2026–27", place_code="BSC", place_label="B.Sc",
        entry_date=dt.date(2026, 6, 1), program=c.program if pinned else None,
        curriculum=c.regulation if pinned else None,
    )  # fmt: skip
    return found
