from rest_framework import serializers

from students.models import GuardianLink, Student


class StudentInput(serializers.Serializer):
    version = serializers.IntegerField()
    full_name = serializers.CharField(max_length=150, required=False)
    date_of_birth = serializers.DateField(allow_null=True, required=False)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    address = serializers.CharField(max_length=500, allow_blank=True, required=False)


def _current(student: Student):
    return student.enrollments.filter(status="active").select_related("campus").first()


def enrollment_item(enrollment) -> dict | None:
    if enrollment is None:
        return None
    return {
        "academic_year": enrollment.academic_year,
        "place_code": enrollment.place_code,
        "place_label": enrollment.place_label,
        "campus_name": enrollment.campus.name if enrollment.campus_id else None,
        "entry_date": enrollment.entry_date,
        "status": enrollment.status,
        "exit_date": enrollment.exit_date,
        "exit_reason": enrollment.exit_reason,
    }


def student_list_item(student: Student) -> dict:
    current = _current(student)
    return {
        "id": str(student.id),
        "number": student.number,
        "full_name": student.person.full_name,
        "status": student.status,
        "left_on": student.left_on,
        "enrollment": enrollment_item(current),
    }


def placements(student: Student) -> list[dict]:
    from academics.models import EnrollmentPeriod

    rows = EnrollmentPeriod.objects.filter(enrollment__student=student).select_related(
        "year", "grade", "program", "section", "campus"
    )
    return [
        {
            "year": row.year.code,
            "grade": row.level.name,  # a college batch's program
            "section": row.section.code,
            "campus": row.campus.name,
            "state": row.state,
            "is_repeat": row.is_repeat,
        }
        for row in rows
    ]


def current_section(student: Student) -> str | None:
    from academics import placement

    return placement.label(placement.current_period(student))


def student_item(student: Student) -> dict:
    person = student.person
    return {
        **student_list_item(student),
        "placements": placements(student),
        "current_section": current_section(student),
        "version": student.version,
        "date_of_birth": person.date_of_birth,
        "phone": person.phone,
        "email": person.email,
        "address": person.address,
        "admitted_on": student.admitted_on,
        "enrollments": [enrollment_item(e) for e in student.enrollments.select_related("campus")],
        "application": {"id": str(student.application_id), "number": student.application.number}
        if student.application_id
        else None,
        "login": student.user.username if student.user_id else None,
        "last_login": student.user.last_login if student.user_id else None,
    }


class AdultInput(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False, default="")
    email = serializers.EmailField(allow_blank=True, required=False, default="")


class ProposeInput(serializers.Serializer):
    adult = AdultInput()
    relationship = serializers.CharField(max_length=40)


class AccessInput(serializers.Serializer):
    record = serializers.BooleanField(required=False, default=True)
    fees = serializers.BooleanField(required=False, default=False)
    messages = serializers.BooleanField(required=False, default=False)


class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=40)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class VerifyInput(serializers.Serializer):
    version = serializers.IntegerField()
    authority_basis = serializers.ChoiceField(GuardianLink.Basis.choices)
    verification_method = serializers.ChoiceField(GuardianLink.Method.choices)
    verification_reference = serializers.CharField(max_length=120, allow_blank=True, required=False, default="")
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
    ends_on = serializers.DateField(required=False, allow_null=True, default=None)
    access = AccessInput(required=False)
    restrictions = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")
    login = LoginInput(required=False, allow_null=True, default=None)


class WithdrawInput(serializers.Serializer):
    version = serializers.IntegerField()
    effective_on = serializers.DateField()
    reason = serializers.CharField(max_length=500, allow_blank=True)
    clearance_note = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")


class RevokeInput(serializers.Serializer):
    version = serializers.IntegerField()
    reason = serializers.CharField(max_length=500, allow_blank=True)


def link_item(link: GuardianLink, full: bool, today) -> dict:
    """A guardian link for staff. Notes and verification evidence only for those who manage links (`full`)."""
    from students.guardians import needs_adult_review

    adult = link.adult
    item = {
        "id": str(link.id),
        "version": link.version,
        "adult": {"full_name": adult.full_name, "phone": adult.phone, "email": adult.email},
        "relationship": link.relationship,
        "status": link.status,
        "status_label": link.get_status_display(),
        "in_effect": link.in_effect(today),
        "access": {"record": link.access_record, "fees": link.access_fees, "messages": link.access_messages},
        "starts_on": link.starts_on,
        "ends_on": link.ends_on,
        "has_login": link.user_id is not None,
        "source": link.source,
        "needs_adult_review": needs_adult_review(link, today),
    }
    if full:
        item.update(
            restrictions=link.restrictions,
            authority_basis=link.authority_basis,
            verification_method=link.verification_method,
            verification_reference=link.verification_reference,
            revoke_reason=link.revoke_reason,
        )
    return item
