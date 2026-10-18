from rest_framework import serializers

from students.models import Student


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
    }


def student_list_item(student: Student) -> dict:
    current = _current(student)
    return {
        "id": str(student.id),
        "number": student.number,
        "full_name": student.person.full_name,
        "status": student.status,
        "enrollment": enrollment_item(current),
    }


def student_item(student: Student) -> dict:
    person = student.person
    return {
        **student_list_item(student),
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
