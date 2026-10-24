"""Programs and courses for colleges, under institution/academics/ (slice 5b §5)."""

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from academics import curricula, offerings, programs
from academics.models import CourseOffering, CurriculumVersion
from academics.serializers import (
    CourseInput,
    CoursePatch,
    CurriculumCourseInput,
    CurriculumCoursePatch,
    CurriculumInput,
    CurriculumPatch,
    OfferingInput,
    OfferingPatch,
    OfferingTeacherInput,
    ProgramInput,
    ProgramPatch,
    VersionInput,
)
from academics.views import AcademicsView, valid
from common.pagination import Pages


class ProgramList(AcademicsView):
    def get(self, request):
        rows = request.institution.programs.select_related("department", "institution")
        return Response([programs.program_item(row, request.user) for row in rows])

    def post(self, request):
        program = programs.save_program(request.user, request.institution, None, valid(ProgramInput, request.data))
        return Response(programs.program_item(program, request.user), status=status.HTTP_201_CREATED)


class ProgramDetail(AcademicsView):
    def get(self, request, pk):
        return Response(programs.program_item(self.found(request.institution.programs, pk), request.user))

    def patch(self, request, pk):
        found = self.found(request.institution.programs, pk)
        data = valid(ProgramPatch, request.data)
        program = programs.save_program(request.user, request.institution, found, data, data.pop("version"))
        return Response(programs.program_item(program, request.user))


class CourseList(AcademicsView):
    pagination_class = Pages

    def get(self, request):
        rows = request.institution.courses.select_related("department", "institution")
        if len(search := request.query_params.get("search", "").strip()) >= 3:
            rows = rows.filter(Q(code__icontains=search) | Q(title__icontains=search))
        page = self.paginate_queryset(rows)
        return self.get_paginated_response([programs.course_item(row, request.user) for row in page])

    def post(self, request):
        course = programs.save_course(request.user, request.institution, None, valid(CourseInput, request.data))
        return Response(programs.course_item(course, request.user), status=status.HTTP_201_CREATED)


class CourseDetail(AcademicsView):
    def patch(self, request, pk):
        found = self.found(request.institution.courses, pk)
        data = valid(CoursePatch, request.data)
        course = programs.save_course(request.user, request.institution, found, data, data.pop("version"))
        return Response(programs.course_item(course, request.user))


class CurriculumList(AcademicsView):
    def get(self, request, pk):
        program = self.found(request.institution.programs, pk)
        return Response([curricula.summary_item(row) for row in program.curricula.all()])

    def post(self, request, pk):
        program = self.found(request.institution.programs.select_related("institution"), pk)
        made = curricula.create(request.user, program, valid(CurriculumInput, request.data))
        return Response(curricula.curriculum_item(made, request.user), status=status.HTTP_201_CREATED)


class CurriculumView(AcademicsView):
    def curriculum(self) -> CurriculumVersion:
        rows = CurriculumVersion.objects.filter(program__institution=self.request.institution)
        return self.found(rows.select_related("program__institution"), self.kwargs["pk"])

    def shown(self, curriculum, created=False) -> Response:
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(curricula.curriculum_item(curriculum, self.request.user), status=code)


class CurriculumDetail(CurriculumView):
    def get(self, request, pk):
        return self.shown(self.curriculum())

    def patch(self, request, pk):
        data = valid(CurriculumPatch, request.data)
        return self.shown(curricula.save(request.user, self.curriculum(), data, data.pop("version")))


class CurriculumCourses(CurriculumView):
    def post(self, request, pk):
        data = valid(CurriculumCourseInput, request.data)
        return self.shown(curricula.add_course(request.user, self.curriculum(), data), created=True)


class CurriculumCourseDetail(CurriculumView):
    def entry(self, curriculum):
        return self.found(curriculum.courses.select_related("course"), self.kwargs["entry"])

    def patch(self, request, pk, entry):
        curriculum = self.curriculum()
        data = valid(CurriculumCoursePatch, request.data)
        return self.shown(curricula.change_course(request.user, curriculum, self.entry(curriculum), data))

    def delete(self, request, pk, entry):
        curriculum = self.curriculum()
        return self.shown(curricula.remove_course(request.user, curriculum, self.entry(curriculum)))


class CurriculumAction(CurriculumView):
    action = staticmethod(curricula.publish)

    def post(self, request, pk):
        version = valid(VersionInput, request.data)["version"]
        result = self.action(request.user, self.curriculum(), version)
        return self.shown(result, created=self.action is curricula.revise)


class OfferingView(AcademicsView):
    def offering(self) -> CourseOffering:
        rows = CourseOffering.objects.filter(institution=self.request.institution)
        rows = rows.select_related("course", "term__year", "campus", "institution", "linked_to__course")
        return self.found(rows, self.kwargs["pk"])

    def shown(self, offering, created=False) -> Response:
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(offerings.offering_item(offering, self.request.user), status=code)


class OfferingList(OfferingView):
    pagination_class = Pages

    def get(self, request):
        rows = CourseOffering.objects.filter(institution=request.institution).select_related(
            "course", "term__year", "campus", "institution", "linked_to__course"
        )
        for name in ("term", "course"):
            if value := request.query_params.get(name):
                rows = rows.filter(**{f"{name}_id": value})
        page = self.paginate_queryset(rows.order_by("-term__starts_on", "course__code", "code"))
        return self.get_paginated_response([offerings.offering_item(row, request.user) for row in page])

    def post(self, request):
        data = valid(OfferingInput, request.data)
        return self.shown(offerings.save_offering(request.user, request.institution, None, data), created=True)


class OfferingDetail(OfferingView):
    def get(self, request, pk):
        return self.shown(self.offering())

    def patch(self, request, pk):
        data = valid(OfferingPatch, request.data)
        found = offerings.save_offering(request.user, request.institution, self.offering(), data, data.pop("version"))
        return self.shown(found)


class OfferingTeachers(OfferingView):
    def post(self, request, pk):
        offering = self.offering()
        offerings.assign_teacher(request.user, offering, valid(OfferingTeacherInput, request.data)["membership"])
        return self.shown(offering, created=True)


class OfferingEndTeaching(OfferingView):
    def post(self, request, pk, assignment):
        offering = self.offering()
        offerings.end_teaching(request.user, offering, self.found(offering.teaching.all(), assignment))
        return self.shown(offering)
