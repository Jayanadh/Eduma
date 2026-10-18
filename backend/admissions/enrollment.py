"""Turning an accepted offer into a student (slice 4a S4-07): a new Person (never merged with anyone), a Student with
its number, an Enrollment, and a student login with a first password. Done once: asking again returns the same
student."""

import datetime as dt

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Membership, User
from accounts.permissions import today_for
from admissions.applications import Stage, wrong_stage
from admissions.models import Application
from admissions.review import can_approve
from common import audit
from configuration.registry import setting
from institutions.models import Institution
from students.models import Enrollment, Person, Student


def enroll(actor, application: Application, version: int, password: str) -> Student:
    existing = Student.objects.filter(application=application).first()
    if existing is not None:
        return existing
    institution = application.institution
    if not can_approve(actor, application):
        raise PermissionDenied("Your role does not cover this application.")
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=institution.pk)  # student numbers are handed out one at a time
        application = Application.objects.select_for_update().select_related("cycle", "place").get(pk=application.pk)
        existing = Student.objects.filter(application=application).first()
        if existing is not None:
            return existing
        application.check_version(version)
        if application.stage != Stage.ACCEPTED:
            raise wrong_stage(application)
        cycle, place = application.cycle, application.place
        number = Student.objects.next_number(institution, cycle.entry_year)
        login = User(
            username=f"{institution.slug}.{number}",
            full_name=application.learner_name,
            must_change_password=True,
            created_by=actor,
        )
        try:
            password_validation.validate_password(password, login)
        except DjangoValidationError as error:
            raise ValidationError({"password": error.messages}) from error
        login.set_password(password)
        login.save()
        Membership.objects.create(institution=institution, user=login, kind=Membership.Kind.STUDENT, created_by=actor)
        person = Person.objects.create(
            institution=institution,
            full_name=application.learner_name,
            date_of_birth=application.date_of_birth,
            address=application.address,
        )
        today = today_for(institution)
        student = Student.objects.create(
            institution=institution,
            person=person,
            number=number,
            admitted_on=today,
            application=application,
            user=login,
        )
        year_starts = dt.date(cycle.entry_year, setting(institution, "academic.year_start"), 1)
        Enrollment.objects.create(
            student=student,
            institution=institution,
            academic_year=cycle.academic_year,
            place_code=place.code,
            place_label=place.label,
            campus=place.campus,
            entry_date=max(year_starts, today),
        )
        application.stage = Stage.ENROLLED
        application.decided_by = actor
        application.save()
        audit.log(
            actor,
            "application.enrolled",
            application,
            f"{application.number}: enrolled as student {number}",
            institution=institution,
            changes={"student": number, "login": login.username},
        )
        return student
