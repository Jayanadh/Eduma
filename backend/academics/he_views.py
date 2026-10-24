"""Programs and courses for colleges, under institution/academics/ (slice 5b §5)."""

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from academics import programs
from academics.serializers import CourseInput, CoursePatch, ProgramInput, ProgramPatch
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
