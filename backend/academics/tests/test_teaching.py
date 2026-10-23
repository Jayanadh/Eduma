"""A teacher's own classes and rosters (slice 5a S5A-05)."""

import datetime as dt

from academics.models import TeachingAssignment
from accounts.models import Membership
from accounts.permissions import today_for
from admissions.tests.conftest import applicant
from testing import factories

from .conftest import API, enrolled_student
from .test_placement import make_section, place

CLASSES = "/api/v1/teaching/classes"


def teach(admin, section, teacher, subject=None):
    body = {"membership": str(Membership.objects.get(user=teacher).id), "subject": str(subject.id) if subject else None}
    return admin.post(f"{API}/sections/{section.id}/teachers", body, format="json")


def test_a_teacher_sees_their_classes_and_rosters(world, admin, school, client_for):
    section, other = make_section(school), make_section(school, code="6B")
    place(admin, section, enrolled_student(world.a, "2026-0001", name="Kiran Rao"))
    place(admin, other, enrolled_student(world.a, "2026-0002", name="Someone Else"))
    teacher = factories.member(world.a, role="teacher")
    teach(admin, section, teacher, school.science)
    me = client_for(world.a.slug, teacher)
    classes = me.get(CLASSES).json()
    assert classes == [
        {
            "section": {"id": str(section.id), "code": "6A", "grade": "Class 6", "year": "2026–27"},
            "subjects": ["Science"],
            "class_teacher": False,
        }
    ]
    roster = me.get(f"{CLASSES}/{section.id}/students").json()
    assert roster == [{"number": "2026-0001", "full_name": "Kiran Rao", "status": "active"}]
    assert me.get(f"{CLASSES}/{other.id}/students").status_code == 404
    assert me.get("/api/v1/institution/students").status_code == 403


def test_an_ended_assignment_closes_the_roster(world, admin, school, client_for):
    """Review Focus 2."""
    section = make_section(school)
    teacher = factories.member(world.a, role="teacher")
    teach(admin, section, teacher)
    TeachingAssignment.objects.update(
        starts_on=today_for(world.a) - dt.timedelta(days=30), ends_on=today_for(world.a) - dt.timedelta(days=1)
    )
    me = client_for(world.a.slug, teacher)
    assert me.get(CLASSES).json() == []
    assert me.get(f"{CLASSES}/{section.id}/students").status_code == 404


def test_class_teacher_flag(world, admin, school, client_for):
    teacher = factories.member(world.a, role="teacher")
    section = make_section(school)
    teach(admin, section, teacher)  # no subject: the whole class, i.e. the class teacher
    assert client_for(world.a.slug, teacher).get(CLASSES).json()[0]["class_teacher"] is True


def test_not_for_families_or_other_hosts(world, admin, school, client_for):
    parent = applicant(world.a, "asha.parent")
    assert client_for(world.a.slug, parent).get(CLASSES).status_code == 404
    assert client_for(None, world.a_admin).get(CLASSES).status_code == 404
