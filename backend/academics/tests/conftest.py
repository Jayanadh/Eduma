import pytest

from admissions.tests.conftest import switch_on

API = "/api/v1/institution/academics"


@pytest.fixture
def on(world):
    switch_on(world.a, modules=("admissions", "students", "academics", "course_registration"))
    return world.a


@pytest.fixture
def admin(world, on, client_for):
    return client_for(world.a.slug, world.a_admin)


def make_year(client, code="2026–27", start="2026-06-01", end="2027-03-31", **extra):
    return client.post(f"{API}/years", {"code": code, "starts_on": start, "ends_on": end, **extra}, format="json")


class School:
    pass


@pytest.fixture
def school(world, on):
    """Aster's 2026–27 year, Class 6 and 7, Science, and Main and City campuses."""
    import datetime as dt

    from academics.models import AcademicYear, GradeLevel, Subject
    from testing import factories

    found = School()
    found.year = AcademicYear.objects.create(
        institution=world.a,
        code="2026–27",
        starts_on=dt.date(2026, 6, 1),
        ends_on=dt.date(2027, 3, 31),
        status="current",
    )
    found.next_year = AcademicYear.objects.create(
        institution=world.a, code="2027–28", starts_on=dt.date(2027, 6, 1), ends_on=dt.date(2028, 3, 31)
    )
    found.c6 = GradeLevel.objects.create(institution=world.a, code="C6", name="Class 6", order=6)
    found.c7 = GradeLevel.objects.create(institution=world.a, code="C7", name="Class 7", order=7)
    found.science = Subject.objects.create(institution=world.a, code="SCI", name="Science")
    found.main = factories.campus(world.a, code="MAIN", name="Main campus")
    found.city = factories.campus(world.a, code="CITY", name="City campus")
    return found


def section_body(school, **changes):
    return {
        "year": str(school.year.id),
        "grade": str(school.c6.id),
        "campus": str(school.main.id),
        "code": "6A",
        "capacity": 40,
        **changes,
    }


def enrolled_student(institution, number, name="Learner", year="2026–27"):
    """A student with an active study episode, as enrollment or an import leaves them."""
    import datetime as dt

    from students.models import Enrollment, Person, Student

    person = Person.objects.create(institution=institution, full_name=name)
    student = Student.objects.create(
        institution=institution, person=person, number=number, admitted_on=dt.date(2026, 4, 1)
    )
    Enrollment.objects.create(
        student=student, institution=institution, academic_year=year, place_code="C6", place_label="Class 6",
        entry_date=dt.date(2026, 6, 1),
    )  # fmt: skip
    return student
