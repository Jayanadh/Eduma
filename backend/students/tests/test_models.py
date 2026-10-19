import datetime as dt

import pytest
from django.db import IntegrityError, transaction
from django.http import Http404

from accounts.permissions import today_for
from configuration.gates import module_on, require_module
from configuration.models import SettingRevision
from students.models import Enrollment, Person, Student


def make_student(institution, number):
    person = Person.objects.create(institution=institution, full_name="Learner")
    return Student.objects.create(
        institution=institution, person=person, number=number, admitted_on=dt.date(2027, 6, 1)
    )


def test_numbers_run_per_institution(world):
    assert Student.objects.next_number(world.a, 2027) == "2027-0001"
    make_student(world.a, "2027-0001")
    assert Student.objects.next_number(world.a, 2027) == "2027-0002"
    assert Student.objects.next_number(world.b, 2027) == "2027-0001"
    assert Student.objects.next_number(world.a, 2028) == "2028-0001"
    with pytest.raises(IntegrityError), transaction.atomic():
        make_student(world.a, "2027-0001")


def test_one_active_enrollment_per_student(world):
    student = make_student(world.a, "2027-0001")

    def enroll(status="active"):
        return Enrollment.objects.create(
            student=student,
            institution=world.a,
            academic_year="2027–28",
            place_code="C1",
            place_label="Class 1",
            entry_date=dt.date(2027, 6, 1),
            status=status,
        )

    enroll()
    enroll(status="ended")
    with pytest.raises(IntegrityError), transaction.atomic():
        enroll()


def test_module_gate_follows_switched_on_modules(world):
    world.a.modules = ["admissions", "students"]
    world.a.save()
    assert not module_on(world.a, "admissions")
    with pytest.raises(Http404):
        require_module(world.a, "admissions")
    SettingRevision.objects.create(
        institution=world.a,
        key="modules.enabled",
        number=1,
        value=["admissions", "students"],
        status="published",
        effective_from=today_for(world.a),
    )
    assert module_on(world.a, "admissions")
    require_module(world.a, "students")
    world.a.modules = ["students"]
    world.a.save()
    assert not module_on(world.a, "admissions")


def link(student, adult, status="proposed", **kw):
    from students.models import GuardianLink

    return GuardianLink.objects.create(
        institution=student.institution, student=student, adult=adult, relationship="Mother", status=status, **kw
    )


def test_one_live_link_per_student_and_adult(world):
    student = make_student(world.a, "2027-0001")
    adult = Person.objects.create(institution=world.a, full_name="Asha Rao")
    first = link(student, adult)
    with pytest.raises(IntegrityError), transaction.atomic():
        link(student, adult, status="active")
    first.status = "revoked"
    first.save()
    link(student, adult)


def test_link_in_effect_follows_dates(world):
    today = today_for(world.a)
    student = make_student(world.a, "2027-0001")
    people = [Person.objects.create(institution=world.a, full_name=f"Adult {n}") for n in range(4)]
    ended = link(
        student,
        people[0],
        status="active",
        starts_on=today - dt.timedelta(days=9),
        ends_on=today - dt.timedelta(days=1),
    )
    proposed = link(student, people[1])
    open_ended = link(student, people[2], status="active", starts_on=today)
    later = link(student, people[3], status="active", starts_on=today + dt.timedelta(days=1))
    assert [row.in_effect(today) for row in (ended, proposed, open_ended, later)] == [False, False, True, False]


def test_employee_number_unique_per_institution_but_blank_repeats(world):
    from accounts.models import Employee, Membership
    from testing import factories

    def employee(institution, number):
        membership = Membership.objects.get(user=factories.member(institution))
        return Employee.objects.create(institution=institution, membership=membership, employee_number=number)

    employee(world.a, "")
    employee(world.a, "")
    employee(world.a, "AST-001")
    employee(world.b, "AST-001")
    with pytest.raises(IntegrityError), transaction.atomic():
        employee(world.a, "AST-001")
