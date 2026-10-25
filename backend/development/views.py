"""Placements, internships, alumni, research and quality evidence: staff under development/, students under
student/ (slice 10c; SCR-048)."""

from django.http import FileResponse, JsonResponse
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import Program
from academics.registration_views import OwnView
from academics.views import valid
from accounts.permissions import has_perm
from accounts.role_views import holds_any
from configuration.gates import require_module
from development import services
from development.models import (
    AlumniProfile,
    Employer,
    EthicsApproval,
    EvidenceRequest,
    EvidenceVersion,
    Internship,
    Milestone,
    Opportunity,
    PlacementApplication,
    ReviewCycle,
    Scholar,
    Supervision,
)


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class DevView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]
    module = "placements"
    perm = services.PLACEMENT

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, self.module)

    def manager(self) -> bool:
        return has_perm(self.request.user, self.request.institution, self.perm)

    def needs(self):
        if not self.manager():
            raise PermissionDenied("You can't see this office's records.")


# Placements


class Employers(DevView):
    def get(self, request):
        self.needs()
        rows = Employer.objects.filter(institution=request.institution).order_by("name")
        return Response([{"id": str(e.id), "name": e.name, "contact": e.contact} for e in rows])

    def post(self, request):
        self.needs()
        name = serializers.CharField(max_length=150).to_internal_value(request.data.get("name", ""))
        made = Employer.objects.create(
            institution=request.institution, name=name.strip(), contact=str(request.data.get("contact", ""))[:150]
        )
        return Response({"id": str(made.id), "name": made.name}, status=status.HTTP_201_CREATED)


class OpportunityInput(serializers.Serializer):
    employer = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=Opportunity.Kind.choices)
    title = serializers.CharField(max_length=150)
    description = serializers.CharField(max_length=4000, allow_blank=True, default="")
    programs = serializers.ListField(child=serializers.UUIDField(), default=list)
    min_cgpa = serializers.DecimalField(
        max_digits=4, decimal_places=2, min_value=0, max_value=10, allow_null=True, default=None
    )
    closes_on = serializers.DateField()


class Opportunities(DevView):
    def get(self, request):
        self.needs()
        rows = Opportunity.objects.filter(institution=request.institution).select_related("employer")
        return Response([services.opportunity_item(o) for o in rows.prefetch_related("programs")])

    def post(self, request):
        self.needs()
        data = valid(OpportunityInput, request.data)
        employer = _found(Employer.objects.filter(institution=request.institution), data.pop("employer"))
        programs = list(Program.objects.filter(institution=request.institution, id__in=data.pop("programs")))
        made = Opportunity.objects.create(institution=request.institution, employer=employer, **data)
        made.programs.set(programs)
        return Response(services.opportunity_item(made), status=status.HTTP_201_CREATED)


class Applications(DevView):
    def get(self, request, pk):
        self.needs()
        opportunity = _found(Opportunity.objects.filter(institution=request.institution), pk)
        rows = opportunity.applications.select_related("opportunity__employer", "student__person")
        return Response([services.application_item(a, office=True) for a in rows])


class ApplicationMove(DevView):
    def post(self, request, pk):
        application = _found(
            PlacementApplication.objects.filter(opportunity__institution=request.institution).select_related(
                "opportunity__employer", "student__person"
            ),
            pk,
        )
        done = services.office_move(request.user, request.institution, application, str(request.data.get("state", "")))
        return Response(services.application_item(done, office=True))


class Report(DevView):
    def get(self, request):
        self.needs()
        return Response(services.report(request.institution))


class Internships(DevView):
    def get(self, request):
        rows = Internship.objects.filter(application__opportunity__institution=request.institution).select_related(
            "application__opportunity__employer", "application__student__person", "supervisor__user"
        )
        if not self.manager():
            rows = rows.filter(supervisor__user=request.user)
        return Response([services.internship_item(i) for i in rows])


class InternshipAction(DevView):
    action = "supervisor"

    def post(self, request, pk):
        internship = _found(
            Internship.objects.filter(application__opportunity__institution=request.institution).select_related(
                "application__opportunity__employer", "application__student__person", "supervisor__user"
            ),
            pk,
        )
        if self.action == "supervisor":
            supervisor = services.staff_member(request.institution, request.data.get("username"))
            done = services.set_supervisor(request.user, request.institution, internship, supervisor)
        else:
            score = serializers.DecimalField(
                max_digits=5, decimal_places=2, min_value=0, max_value=100
            ).to_internal_value(request.data.get("score"))
            done = services.evaluate(
                request.user, request.institution, internship, score, str(request.data.get("remarks", ""))[:2000]
            )
        return Response(services.internship_item(done))


class Alumni(DevView):
    def get(self, request):
        self.needs()
        rows = AlumniProfile.objects.filter(
            student__institution=request.institution, consented_at__isnull=False, withdrawn_at__isnull=True
        ).select_related("student__person")
        return Response([services.alumni_item(p) for p in rows])


# Research


class ResearchView(DevView):
    module = "quality"
    perm = services.RESEARCH

    def scholar(self, pk) -> Scholar:
        return _found(services.scholars_for(self.request.user, self.request.institution), pk)


class ScholarInput(serializers.Serializer):
    student = serializers.UUIDField()
    topic = serializers.CharField(max_length=250)
    started_on = serializers.DateField()


class Scholars(ResearchView):
    def get(self, request):
        return Response([services.scholar_item(s) for s in services.scholars_for(request.user, request.institution)])

    def post(self, request):
        self.needs()
        data = valid(ScholarInput, request.data)
        student = _found(request.institution.students.select_related("person"), data.pop("student"))
        if Scholar.objects.filter(student=student).exists():
            raise serializers.ValidationError({"student": ["Already a research scholar."]})
        made = Scholar.objects.create(institution=request.institution, student=student, **data)
        return Response(services.scholar_item(made), status=status.HTTP_201_CREATED)


class ScholarDetail(ResearchView):
    def get(self, request, pk):
        return Response(services.scholar_item(self.scholar(pk)))


class EthicsInput(serializers.Serializer):
    reference = serializers.CharField(max_length=60)
    committee = serializers.CharField(max_length=120)
    valid_from = serializers.DateField()
    valid_to = serializers.DateField()


class MilestoneInput(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    due_on = serializers.DateField()
    needs_ethics = serializers.BooleanField(default=False)


class ScholarAction(ResearchView):
    action = "supervisors"

    def post(self, request, pk):
        self.needs()
        scholar = self.scholar(pk)
        if self.action == "supervisors":
            supervisor = services.staff_member(request.institution, request.data.get("username"))
            role = "co" if request.data.get("role") == "co" else "main"
            Supervision.objects.create(
                scholar=scholar, supervisor=supervisor, role=role, starts_on=services.today_for(request.institution)
            )
        elif self.action == "ethics":
            data = valid(EthicsInput, request.data)
            if data["valid_to"] < data["valid_from"]:
                raise serializers.ValidationError({"valid_to": ["Ends before it starts."]})
            EthicsApproval.objects.create(scholar=scholar, **data)
        else:
            Milestone.objects.create(scholar=scholar, **valid(MilestoneInput, request.data))
        return Response(services.scholar_item(scholar), status=status.HTTP_201_CREATED)


class EndSupervision(ResearchView):
    def post(self, request, pk):
        self.needs()
        supervision = _found(Supervision.objects.filter(scholar__institution=request.institution), pk)
        supervision.ends_on = services.today_for(request.institution)
        supervision.save(update_fields=["ends_on"])
        return Response(services.scholar_item(supervision.scholar))


class MilestoneDecision(ResearchView):
    action = "approve"

    def post(self, request, pk):
        milestone = _found(Milestone.objects.filter(scholar__institution=request.institution), pk)
        if not services.supervising(request.user, request.institution).filter(scholar=milestone.scholar).exists():
            raise NotFound()
        done = services.decide_milestone(
            request.user,
            request.institution,
            milestone,
            self.action == "approve",
            str(request.data.get("note", ""))[:500],
        )
        return Response(services.scholar_item(done.scholar))


# Quality evidence


class QualityView(DevView):
    module = "quality"
    perm = services.QUALITY


class Cycles(QualityView):
    def get(self, request):
        self.needs()
        return Response([services.cycle_item(c) for c in ReviewCycle.objects.filter(institution=request.institution)])

    def post(self, request):
        self.needs()
        framework = serializers.CharField(max_length=60).to_internal_value(request.data.get("framework", ""))
        period = serializers.CharField(max_length=30).to_internal_value(request.data.get("period", ""))
        made = ReviewCycle.objects.create(institution=request.institution, framework=framework, period=period)
        return Response(services.cycle_item(made, requests=True), status=status.HTTP_201_CREATED)


class CycleDetail(QualityView):
    def cycle(self, pk):
        self.needs()
        return _found(ReviewCycle.objects.filter(institution=self.request.institution), pk)

    def get(self, request, pk):
        return Response(services.cycle_item(self.cycle(pk), requests=True))


class CycleAction(CycleDetail):
    action = "requests"

    def post(self, request, pk):
        cycle = self.cycle(pk)
        if self.action == "freeze":
            return Response(
                services.cycle_item(services.freeze(request.user, request.institution, cycle), requests=True)
            )
        if cycle.frozen_at:
            raise services.Problem(409, "cycle_frozen", "This review cycle is frozen.")
        criterion = serializers.CharField(max_length=20).to_internal_value(request.data.get("criterion", ""))
        title = serializers.CharField(max_length=200).to_internal_value(request.data.get("title", ""))
        owner = services.staff_member(request.institution, request.data.get("username"))
        EvidenceRequest.objects.create(cycle=cycle, criterion=criterion, title=title, owner=owner)
        return Response(services.cycle_item(cycle, requests=True), status=status.HTTP_201_CREATED)

    def get(self, request, pk):
        """The frozen snapshot as a JSON file."""
        cycle = self.cycle(pk)
        if self.action != "export" or not cycle.frozen_at:
            raise NotFound()
        body = {**cycle.snapshot, "snapshot_sha256": cycle.snapshot_hash, "frozen_at": cycle.frozen_at.isoformat()}
        response = JsonResponse(body, json_dumps_params={"indent": 2})
        response["Content-Disposition"] = f'attachment; filename="evidence-{cycle.framework}-{cycle.period}.json"'
        return response


def _requests(institution):
    return EvidenceRequest.objects.filter(cycle__institution=institution).select_related("cycle", "owner__user")


class MyEvidence(QualityView):
    def get(self, request):
        rows = _requests(request.institution).filter(owner__user=request.user)
        return Response([services.request_item(r) for r in rows])


class EvidenceAction(QualityView):
    action = "upload"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        found = _requests(request.institution).filter(pk=pk).first()
        if found is None or not (found.owner.user_id == request.user.id or self.manager()):
            raise NotFound()
        if self.action == "upload":
            services.upload(request.user, found, request.FILES.get("file"))
        else:
            note = str(request.data.get("note", ""))[:500]
            services.review(request.user, request.institution, found, self.action == "accept", note)
        return Response(services.request_item(_requests(request.institution).get(pk=pk)))


class EvidenceFile(QualityView):
    def get(self, request, pk):
        version = _found(
            EvidenceVersion.objects.filter(request__cycle__institution=request.institution).select_related(
                "request__owner"
            ),
            pk,
        )
        if not (version.request.owner.user_id == request.user.id or self.manager()):
            raise NotFound()
        return FileResponse(version.file.open("rb"), content_type=version.content_type, filename=version.original_name)


# Students' own pages


class OwnPlacements(OwnView):
    module = "placements"

    def get(self, request):
        today = services.today_for(request.institution)
        open_rows = Opportunity.objects.filter(institution=request.institution, closes_on__gte=today)
        mine = self.me.placement_applications.select_related("opportunity__employer")
        alumni = AlumniProfile.objects.filter(student=self.me).first()
        return Response(
            {
                "opportunities": [
                    {**services.opportunity_item(o), "eligibility": services.eligibility(self.me, o)}
                    for o in open_rows.select_related("employer").prefetch_related("programs")
                ],
                "applications": [services.application_item(a) for a in mine],
                "alumni": services.alumni_item(alumni) if alumni else None,
            }
        )


class OwnApply(OwnView):
    module = "placements"

    def post(self, request, pk):
        opportunity = _found(Opportunity.objects.filter(institution=request.institution).select_related("employer"), pk)
        made = services.apply(self.me, opportunity, request.data.get("consent") is True)
        return Response(services.application_item(made), status=status.HTTP_201_CREATED)


class OwnDecide(OwnView):
    module = "placements"

    def post(self, request, pk):
        application = _found(self.me.placement_applications.select_related("opportunity__employer"), pk)
        choice = request.data.get("decision")
        if choice not in ("accept", "decline", "withdraw"):
            raise serializers.ValidationError({"decision": ["Accept, decline or withdraw."]})
        done = services.student_decides(application, None if choice == "withdraw" else choice == "accept")
        return Response(services.application_item(done))


class AlumniInput(serializers.Serializer):
    consent = serializers.BooleanField()
    email = serializers.EmailField(allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, allow_blank=True, default="")
    occupation = serializers.CharField(max_length=150, allow_blank=True, default="")


class OwnAlumni(OwnView):
    module = "placements"

    def put(self, request):
        return Response(services.alumni_item(services.save_alumni(self.me, valid(AlumniInput, request.data))))

    def delete(self, request):
        services.withdraw_alumni(self.me)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnResearch(OwnView):
    module = "quality"

    def get(self, request):
        scholar = Scholar.objects.filter(student=self.me).first()
        return Response(services.scholar_item(scholar) if scholar else None)


class OwnMilestone(OwnView):
    module = "quality"

    def post(self, request, pk):
        milestone = _found(Milestone.objects.filter(scholar__student=self.me).select_related("scholar"), pk)
        done = services.submit_milestone(milestone.scholar, milestone, str(request.data.get("summary", ""))[:4000])
        return Response(services.scholar_item(done.scholar))
