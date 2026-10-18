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
