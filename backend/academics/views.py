"""Academic structure for staff, under institution/academics/ (slice 5a §5)."""

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics import moveup, placement, sections, structure, teaching
from academics.models import EnrollmentPeriod, GradeLevel, Section, Subject, Term
from academics.serializers import (
    GradeInput,
    GradePatch,
    MoveInput,
    MoveUpInput,
    PlaceInput,
    SectionInput,
    SectionPatch,
    SubjectInput,
    SubjectPatch,
    TeacherInput,
    TermInput,
    TermPatch,
    YearInput,
    YearPatch,
    named_item,
    term_item,
    year_item,
)
from accounts.models import Membership
from accounts.role_views import holds_any
from common.pagination import Pages
from configuration.gates import require_module


def valid(serializer_class, data) -> dict:
    found = serializer_class(data=data)
    found.is_valid(raise_exception=True)
    return dict(found.validated_data)


class AcademicsView(GenericAPIView):
    """Any staff member reads the structure; changes need academic_structure.manage (checked again for scope)."""

    def get_permissions(self):
        return [holds_any("institution.read" if self.request.method == "GET" else structure.MANAGE)()]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "academics")

    def found(self, queryset, pk):
        row = queryset.filter(pk=pk).first()
        if row is None:
            raise NotFound()
        return row


class YearList(AcademicsView):
    def get(self, request):
        years = request.institution.academic_years.prefetch_related("terms")
        return Response([year_item(year) for year in years])

    def post(self, request):
        year = structure.save_year(request.user, request.institution, None, valid(YearInput, request.data))
        return Response(year_item(year), status=status.HTTP_201_CREATED)


class YearDetail(AcademicsView):
    def get(self, request, pk):
        return Response(year_item(self.found(request.institution.academic_years, pk)))

    def patch(self, request, pk):
        year = self.found(request.institution.academic_years, pk)
        data = valid(YearPatch, request.data)
        return Response(
            year_item(structure.save_year(request.user, request.institution, year, data, data.pop("version")))
        )

    def delete(self, request, pk):
        structure.delete_year(request.user, self.found(request.institution.academic_years, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TermList(AcademicsView):
    def post(self, request, pk):
        year = self.found(request.institution.academic_years, pk)
        term = structure.save_term(request.user, year, None, valid(TermInput, request.data))
        return Response(term_item(term), status=status.HTTP_201_CREATED)


class TermDetail(AcademicsView):
    def term(self, pk) -> Term:
        return self.found(Term.objects.filter(year__institution=self.request.institution), pk)

    def patch(self, request, pk):
        term = self.term(pk)
        return Response(term_item(structure.save_term(request.user, term.year, term, valid(TermPatch, request.data))))

    def delete(self, request, pk):
        term = self.term(pk)
        structure.require_whole(request.user, request.institution)
        term.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NamedList(AcademicsView):
    model = GradeLevel
    create = GradeInput

    def get(self, request):
        return Response([named_item(row) for row in self.model.objects.filter(institution=request.institution)])

    def post(self, request):
        row = structure.save_named(
            request.user, request.institution, self.model, None, valid(self.create, request.data)
        )
        return Response(named_item(row), status=status.HTTP_201_CREATED)


class NamedDetail(AcademicsView):
    model = GradeLevel
    patch_input = GradePatch

    def patch(self, request, pk):
        row = self.found(self.model.objects.filter(institution=request.institution), pk)
        data = valid(self.patch_input, request.data)
        row = structure.save_named(request.user, request.institution, self.model, row, data, data.pop("version"))
        return Response(named_item(row))


class GradeList(NamedList):
    model, create = GradeLevel, GradeInput


class GradeDetail(NamedDetail):
    model, patch_input = GradeLevel, GradePatch


class SubjectList(NamedList):
    model, create = Subject, SubjectInput


class SubjectDetail(NamedDetail):
    model, patch_input = Subject, SubjectPatch


class SectionView(AcademicsView):
    def section(self) -> Section:
        found = Section.objects.filter(institution=self.request.institution, pk=self.kwargs["pk"])
        return self.found(found.select_related("year", "grade", "campus", "institution"), self.kwargs["pk"])


class SectionList(SectionView):
    pagination_class = Pages

    def get(self, request):
        rows = Section.objects.filter(institution=request.institution).select_related(
            "year", "grade", "campus", "institution"
        )
        for name in ("year", "grade", "campus"):
            if value := request.query_params.get(name):
                rows = rows.filter(**{f"{name}_id": value})
        page = self.paginate_queryset(rows.order_by("-year__starts_on", "grade__order", "code"))
        return self.get_paginated_response([sections.section_item(row, request.user) for row in page])

    def post(self, request):
        section = sections.save_section(request.user, request.institution, None, valid(SectionInput, request.data))
        return Response(sections.section_item(section, request.user), status=status.HTTP_201_CREATED)


class SectionDetail(SectionView):
    def get(self, request, pk):
        return Response(sections.section_item(self.section(), request.user))

    def patch(self, request, pk):
        found = self.section()
        data = valid(SectionPatch, request.data)
        section = sections.save_section(request.user, request.institution, found, data, data.pop("version"))
        return Response(sections.section_item(section, request.user))


class Teachers(SectionView):
    def post(self, request, pk):
        section = self.section()
        data = valid(TeacherInput, request.data)
        sections.assign_teacher(request.user, section, data["membership"], data["subject"])
        return Response(sections.section_item(section, request.user), status=status.HTTP_201_CREATED)


class EndTeaching(SectionView):
    def post(self, request, pk, assignment):
        section = self.section()
        found = self.found(section.teaching.all(), assignment)
        sections.end_teaching(request.user, found)
        return Response(sections.section_item(section, request.user))


class Roster(SectionView):
    """Managers of the section's campus and the section's own teachers read it; managers place students."""

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "GET" else super().get_permissions()

    def get(self, request, pk):
        section = self.section_for_roster()
        rows = section.placements.filter(state=EnrollmentPeriod.State.ACTIVE).select_related(
            "enrollment__student__person"
        )
        return Response([placement.roster_item(row) for row in rows.order_by("enrollment__student__number")])

    def section_for_roster(self) -> Section:
        if self.request.site_kind != "institution":
            raise NotFound()
        section = self.section()
        if not (
            sections.can_manage_section(self.request.user, section) or teaching.teaches(self.request.user, section)
        ):
            raise NotFound()
        return section

    def post(self, request, pk):
        section = self.section()
        made = placement.place(request.user, section, valid(PlaceInput, request.data)["students"])
        return Response([placement.roster_item(row) for row in made], status=status.HTTP_201_CREATED)


class Placement(SectionView):
    def period(self) -> EnrollmentPeriod:
        rows = self.section().placements.filter(state=EnrollmentPeriod.State.ACTIVE)
        found = rows.select_related("enrollment__student__person", "section__year").filter(
            enrollment__student_id=self.kwargs["student"]
        )
        if (period := found.first()) is None:
            raise NotFound()
        return period

    def delete(self, request, pk, student):
        placement.end(request.user, self.period())
        return Response(status=status.HTTP_204_NO_CONTENT)


class Move(Placement):
    def post(self, request, pk, student):
        period = self.period()
        target = self.found(
            Section.objects.filter(institution=request.institution), valid(MoveInput, request.data)["section"]
        )
        return Response(placement.roster_item(placement.move(request.user, period, target)))


class MoveUpView(SectionView):
    def sections(self):
        source = self.section()
        data = valid(MoveUpInput, self.request.data)
        found = Section.objects.filter(institution=self.request.institution).select_related("year", "grade", "campus")
        return source, self.found(found, data["target"]), data


class MoveUpPreview(MoveUpView):
    def post(self, request, pk):
        source, target, data = self.sections()
        return Response(moveup.preview(request.user, source, target, data["mode"]))


class MoveUp(MoveUpView):
    def post(self, request, pk):
        source, target, data = self.sections()
        return Response(moveup.commit(request.user, source, target, data["mode"], data["students"]))


class StaffChoices(AcademicsView):
    """Staff to choose from as class or subject teachers; for those who set up sections."""

    def get_permissions(self):
        return [holds_any(structure.MANAGE)()]

    def get(self, request):
        staff = request.institution.memberships.filter(kind=Membership.Kind.STAFF, status=Membership.Status.ACTIVE)
        rows = staff.select_related("user").order_by("user__full_name")
        return Response([{"id": str(row.id), "full_name": row.user.full_name} for row in rows])
