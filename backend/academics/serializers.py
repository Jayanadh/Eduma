from rest_framework import serializers

from academics.models import AcademicYear, Course, CourseOffering, CurriculumCourse


class YearInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    status = serializers.ChoiceField(AcademicYear.Status.choices, required=False)


class YearPatch(YearInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False)


class TermInput(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    ordinal = serializers.IntegerField(min_value=1, max_value=12)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class TermPatch(TermInput):
    name = serializers.CharField(max_length=40, required=False)
    ordinal = serializers.IntegerField(min_value=1, max_value=12, required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False)


class GradeInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=60)
    order = serializers.IntegerField(min_value=0, max_value=1000, required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)


class SubjectInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=80)
    is_active = serializers.BooleanField(required=False, default=True)


class GradePatch(GradeInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    name = serializers.CharField(max_length=60, required=False)
    order = serializers.IntegerField(min_value=0, max_value=1000, required=False)
    is_active = serializers.BooleanField(required=False)


class SubjectPatch(SubjectInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    name = serializers.CharField(max_length=80, required=False)
    is_active = serializers.BooleanField(required=False)


def term_item(term) -> dict:
    return {
        "id": str(term.id),
        "name": term.name,
        "ordinal": term.ordinal,
        "starts_on": term.starts_on,
        "ends_on": term.ends_on,
    }


def year_item(year) -> dict:
    return {
        "id": str(year.id),
        "version": year.version,
        "code": year.code,
        "starts_on": year.starts_on,
        "ends_on": year.ends_on,
        "status": year.status,
        "status_label": year.get_status_display(),
        "terms": [term_item(term) for term in year.terms.all()],
    }


def named_item(row) -> dict:
    item = {"id": str(row.id), "version": row.version, "code": row.code, "name": row.name, "is_active": row.is_active}
    if hasattr(row, "order"):
        item["order"] = row.order
    return item


class SectionInput(serializers.Serializer):
    year = serializers.UUIDField()
    grade = serializers.UUIDField()
    campus = serializers.UUIDField()
    code = serializers.CharField(max_length=20)
    capacity = serializers.IntegerField(min_value=1, max_value=1000)
    class_teacher = serializers.UUIDField(required=False, allow_null=True)


class SectionPatch(SectionInput):
    version = serializers.IntegerField()
    year = serializers.UUIDField(required=False)
    grade = serializers.UUIDField(required=False)
    campus = serializers.UUIDField(required=False)
    code = serializers.CharField(max_length=20, required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=1000, required=False)


class TeacherInput(serializers.Serializer):
    membership = serializers.UUIDField()
    subject = serializers.UUIDField(required=False, allow_null=True, default=None)


class PlaceInput(serializers.Serializer):
    students = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=200)


class MoveInput(serializers.Serializer):
    section = serializers.UUIDField()


class MoveUpInput(serializers.Serializer):
    target = serializers.UUIDField()
    mode = serializers.ChoiceField(["promote", "repeat"])
    students = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=1000)


class ProgramInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=120)
    qualification = serializers.CharField(max_length=40)
    length_terms = serializers.IntegerField(min_value=1, max_value=16)
    department = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class ProgramPatch(ProgramInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    name = serializers.CharField(max_length=120, required=False)
    qualification = serializers.CharField(max_length=40, required=False)
    length_terms = serializers.IntegerField(min_value=1, max_value=16, required=False)


class CourseInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    title = serializers.CharField(max_length=150)
    credits = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=0, max_value=30)
    kind = serializers.ChoiceField(Course.Kind.choices)
    department = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)

    def validate_credits(self, value):
        if value * 2 % 1:
            raise serializers.ValidationError("Credits go in halves: 3, 3.5, 4…")
        return value


class CoursePatch(CourseInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    title = serializers.CharField(max_length=150, required=False)
    credits = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=0, max_value=30, required=False)
    kind = serializers.ChoiceField(Course.Kind.choices, required=False)


class CurriculumInput(serializers.Serializer):
    regulation = serializers.CharField(max_length=20)
    cohort = serializers.IntegerField(min_value=2000, max_value=2100)
    credits_required = serializers.DecimalField(max_digits=6, decimal_places=1, min_value=0)


class CurriculumPatch(serializers.Serializer):
    version = serializers.IntegerField()
    cohort = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    credits_required = serializers.DecimalField(max_digits=6, decimal_places=1, min_value=0, required=False)


class CurriculumCourseInput(serializers.Serializer):
    course = serializers.UUIDField()
    category = serializers.ChoiceField(CurriculumCourse.Category.choices)
    term = serializers.IntegerField(min_value=1, max_value=16)
    elective_group = serializers.CharField(max_length=40, required=False, allow_blank=True)
    prerequisites = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=20)


class CurriculumCoursePatch(CurriculumCourseInput):
    course = None
    category = serializers.ChoiceField(CurriculumCourse.Category.choices, required=False)
    term = serializers.IntegerField(min_value=1, max_value=16, required=False)


class VersionInput(serializers.Serializer):
    version = serializers.IntegerField()


class OfferingInput(serializers.Serializer):
    course = serializers.UUIDField()
    term = serializers.UUIDField()
    campus = serializers.UUIDField()
    code = serializers.CharField(max_length=20)
    capacity = serializers.IntegerField(min_value=1, max_value=2000)
    linked_to = serializers.UUIDField(required=False, allow_null=True)


class OfferingPatch(serializers.Serializer):
    version = serializers.IntegerField()
    campus = serializers.UUIDField(required=False)
    code = serializers.CharField(max_length=20, required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=2000, required=False)
    status = serializers.ChoiceField(CourseOffering.Status.choices, required=False)
    linked_to = serializers.UUIDField(required=False, allow_null=True)


class OfferingTeacherInput(serializers.Serializer):
    membership = serializers.UUIDField()
