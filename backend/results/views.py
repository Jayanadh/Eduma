"""Results for staff (institution/results/), students (student/), and public verification (slice 7)."""

from decimal import Decimal

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from academics.models import AcademicYear, Course, Term
from academics.registration_views import OwnView
from academics.views import valid
from accounts.role_views import holds_any
from configuration.gates import require_module
from results import services
from results.models import Assessment, Candidate, IssuedDocument, Mark, RevisionCase, Scheme


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class ComponentInput(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    max_marks = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0.01"))
    weight = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.01"), max_value=100)
    min_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, allow_null=True
    )


class BandInput(serializers.Serializer):
    min = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    grade = serializers.CharField(max_length=10)
    point = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10)


class SchemeInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    pass_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False)
    decimals = serializers.IntegerField(min_value=0, max_value=4, required=False)
    bands = BandInput(many=True)
    components = ComponentInput(many=True)

    def validate_bands(self, value):
        return [{"min": str(b["min"]), "grade": b["grade"], "point": str(b["point"])} for b in value]


class SchemePatch(SchemeInput):
    version = serializers.IntegerField()
    name = serializers.CharField(max_length=120, required=False)
    bands = BandInput(many=True, required=False)
    components = ComponentInput(many=True, required=False)


class AssessmentInput(serializers.Serializer):
    scheme = serializers.UUIDField()
    term = serializers.UUIDField()
    title = serializers.CharField(max_length=120)
    section = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.UUIDField(required=False, allow_null=True)
    offering = serializers.UUIDField(required=False, allow_null=True)


class MarkInput(serializers.Serializer):
    candidate = serializers.UUIDField()
    component = serializers.UUIDField()
    status = serializers.ChoiceField(Mark.Status.choices)
    score = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)


class MarksInput(serializers.Serializer):
    version = serializers.IntegerField()
    marks = MarkInput(many=True)


class ResultsView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "exams")

    def assessment(self) -> Assessment:
        rows = Assessment.objects.filter(institution=self.request.institution).select_related(
            "scheme", "term", "section", "subject", "offering__course"
        )
        found = _found(rows, self.kwargs["pk"])
        if not services.can_see(self.request.user, found):
            raise NotFound()
        return found

    def student(self, pk):
        from students.views import visible_students

        return _found(visible_students(self.request.user, self.request.institution).select_related("person"), pk)


class Schemes(ResultsView):
    def get(self, request):
        return Response([services.scheme_item(s) for s in Scheme.objects.filter(institution=request.institution)])

    def post(self, request):
        made = services.save_scheme(request.user, request.institution, None, valid(SchemeInput, request.data))
        return Response(services.scheme_item(made), status=status.HTTP_201_CREATED)


class SchemeDetail(ResultsView):
    def patch(self, request, pk):
        found = _found(Scheme.objects.filter(institution=request.institution), pk)
        data = valid(SchemePatch, request.data)
        return Response(
            services.scheme_item(
                services.save_scheme(request.user, request.institution, found, data, data.pop("version"))
            )
        )


class PublishScheme(ResultsView):
    def post(self, request, pk):
        found = _found(Scheme.objects.filter(institution=request.institution), pk)
        return Response(
            services.scheme_item(services.publish_scheme(request.user, found, int(request.data.get("version", 0))))
        )


class ReviseScheme(ResultsView):
    def post(self, request, pk):
        found = _found(Scheme.objects.filter(institution=request.institution), pk)
        return Response(
            services.scheme_item(services.revise_scheme(request.user, found)), status=status.HTTP_201_CREATED
        )


class Assessments(ResultsView):
    def get(self, request):
        rows = Assessment.objects.filter(institution=request.institution).select_related(
            "scheme", "term", "section", "subject", "offering__course"
        )
        for name in ("term", "section", "offering"):
            if value := request.query_params.get(name):
                rows = rows.filter(**{f"{name}_id": value})
        mine = [a for a in rows if services.can_see(request.user, a)]
        return Response(
            [{k: v for k, v in services.assessment_item(a, request.user).items() if k != "candidates"} for a in mine]
        )

    def post(self, request):
        made = services.create_assessment(request.user, request.institution, valid(AssessmentInput, request.data))
        return Response(services.assessment_item(made, request.user), status=status.HTTP_201_CREATED)


class AssessmentDetail(ResultsView):
    def get(self, request, pk):
        return Response(services.assessment_item(self.assessment(), request.user))


class SaveMarks(ResultsView):
    def post(self, request, pk):
        data = valid(MarksInput, request.data)
        made = services.save_marks(request.user, self.assessment(), data["version"], data["marks"])
        return Response(services.assessment_item(made, request.user))


class Step(ResultsView):
    action = "submit"

    def post(self, request, pk):
        a, version = self.assessment(), int(request.data.get("version", 0))
        if self.action == "submit":
            done = services.submit(request.user, a, version)
        elif self.action == "moderate":
            done = services.moderate(request.user, a, version)
        elif self.action == "return":
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise serializers.ValidationError({"reason": ["Say what to check."]})
            done = services.moderate(request.user, a, version, back=reason)
        else:
            done = services.publish(request.user, a, version)
        return Response(services.assessment_item(done, request.user))


class CaseInput(serializers.Serializer):
    reason = serializers.CharField(max_length=300)
    marks = serializers.DictField()


class Cases(ResultsView):
    def post(self, request, pk):
        candidate = _found(
            Candidate.objects.filter(assessment__institution=request.institution).select_related("assessment__scheme"),
            pk,
        )
        data = valid(CaseInput, request.data)
        case = services.open_case(request.user, candidate, data["reason"], data["marks"])
        return Response({"id": str(case.id), "state": case.state}, status=status.HTTP_201_CREATED)


class DecideCase(ResultsView):
    approve = True

    def post(self, request, pk):
        case = _found(RevisionCase.objects.filter(candidate__assessment__institution=request.institution), pk)
        done = services.decide_case(request.user, case, self.approve)
        return Response({"id": str(done.id), "state": done.state})


class DocumentInput(serializers.Serializer):
    kind = serializers.ChoiceField(IssuedDocument.Kind.choices)
    term = serializers.UUIDField(required=False, allow_null=True)
    exception = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class Documents(ResultsView):
    def get(self, request, pk):
        return Response([services.document_item(d) for d in self.student(pk).documents.all()])

    def post(self, request, pk):
        student = self.student(pk)
        data = valid(DocumentInput, request.data)
        if data["kind"] == "report_card":
            require_module(request.institution, "report_cards")
            term = _found(
                Term.objects.filter(year__institution=request.institution).select_related("year"), data.get("term")
            )
            made = services.report_card(request.user, student, term)
        elif data["kind"] == "transcript":
            made = services.transcript(request.user, student)
        else:
            made = services.award(request.user, student, data["exception"])
        return Response(services.document_item(made), status=status.HTTP_201_CREATED)


class Revoke(ResultsView):
    def post(self, request, pk):
        found = _found(IssuedDocument.objects.filter(institution=request.institution), pk)
        return Response(
            services.document_item(services.revoke(request.user, found, str(request.data.get("reason", ""))))
        )


class PromotionInput(serializers.Serializer):
    year = serializers.UUIDField()
    decision = serializers.ChoiceField(["promote", "repeat", "hold"])
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class Promotion(ResultsView):
    def post(self, request, pk):
        student = self.student(pk)
        data = valid(PromotionInput, request.data)
        year = _found(AcademicYear.objects.filter(institution=request.institution), data["year"])
        enrollment = student.enrollments.filter(status="active").first() or student.enrollments.first()
        made = services.decide_promotion(request.user, enrollment, year, data["decision"], data["reason"])
        return Response({"decision": made.decision, "label": made.get_decision_display()})


class Outcomes(ResultsView):
    def get(self, request, pk):
        course = _found(Course.objects.filter(institution=request.institution), pk)
        return Response(
            [{"id": str(o.id), "code": o.code, "description": o.description} for o in course.outcomes.all()]
        )

    def post(self, request, pk):
        course = _found(Course.objects.filter(institution=request.institution), pk)
        code, description = str(request.data.get("code", "")).strip(), str(request.data.get("description", "")).strip()
        if not code or not description:
            raise serializers.ValidationError({"code": ["Give a code and a description."]})
        made = services.add_outcome(request.user, course, {"code": code, "description": description})
        return Response(
            {"id": str(made.id), "code": made.code, "description": made.description}, status=status.HTTP_201_CREATED
        )


class Mappings(ResultsView):
    def post(self, request, pk):
        made = services.map_outcome(
            request.user, self.assessment(), request.data.get("component"), request.data.get("outcome")
        )
        return Response({"id": str(made.id)}, status=status.HTTP_201_CREATED)


class Attainment(ResultsView):
    def post(self, request, pk):
        from decimal import InvalidOperation

        try:
            threshold = Decimal(str(request.data.get("threshold_percent", "60")))
        except InvalidOperation as error:
            raise serializers.ValidationError({"threshold_percent": ["Give a percentage."]}) from error
        run = services.attainment(request.user, self.assessment(), threshold)
        return Response(
            {"id": str(run.id), "threshold_percent": str(run.threshold_percent), "results": run.results},
            status=status.HTTP_201_CREATED,
        )


class AffiliationAward(ResultsView):
    def post(self, request):
        from affiliations import services as affiliation
        from affiliations.models import SubmissionRow

        rows = SubmissionRow.objects.filter(batch__in=affiliation.received(request.institution), status="accepted")
        row = _found(rows.select_related("batch__grant__college"), request.data.get("row"))
        return Response(
            services.document_item(services.award_affiliated(request.user, request.institution, row)),
            status=status.HTTP_201_CREATED,
        )


class Verify(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        found = IssuedDocument.objects.filter(token=token).select_related("institution").first()
        if found is None:
            raise NotFound()
        return Response(services.verification(found))


class OwnResults(OwnView):
    def get(self, request):
        require_module(request.institution, "exams")
        rows = services.ResultVersion.objects.filter(
            candidate__enrollment__student=self.me, superseded_at__isnull=True
        ).select_related(
            "candidate__assessment__term", "candidate__assessment__subject", "candidate__assessment__offering__course"
        )
        return Response(
            [
                {
                    "assessment": r.candidate.assessment.title,
                    "term": r.candidate.assessment.term.name,
                    **services.result_item(r),
                }
                for r in rows.order_by("-published_at")
            ]
        )


class OwnDocuments(OwnView):
    def get(self, request):
        require_module(request.institution, "exams")
        return Response([services.document_item(d) for d in self.me.documents.exclude(status="revoked")])
