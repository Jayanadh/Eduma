"""Affiliation: the console proposes grants; colleges approve them and send batches; universities review (slice 5e)."""

from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import Term
from academics.views import valid
from accounts.role_views import holds_any
from affiliations import services
from affiliations.models import AffiliationGrant, SubmissionBatch
from configuration.gates import require_module
from institutions.models import Institution
from sites.permissions import PlatformAdmin

found = services.found_or_404


class ProposeInput(serializers.Serializer):
    college = serializers.UUIDField()
    university = serializers.UUIDField()
    purpose = serializers.CharField(max_length=300)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    evidence = serializers.CharField(max_length=500)


class ConsoleGrants(GenericAPIView):
    permission_classes = [PlatformAdmin]

    def get(self, request):
        rows = AffiliationGrant.objects.select_related("college", "university")
        return Response([services.grant_item(g) for g in rows])

    def post(self, request):
        data = valid(ProposeInput, request.data)
        data["college"] = found(Institution.objects.all(), data["college"])
        data["university"] = found(Institution.objects.all(), data["university"])
        return Response(services.grant_item(services.propose(request.user, data)), status=status.HTTP_201_CREATED)


class InstitutionView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "academics")

    def mine(self):
        from django.db.models import Q

        institution = self.request.institution
        rows = AffiliationGrant.objects.filter(Q(college=institution) | Q(university=institution))
        return rows.select_related("college", "university")

    def own_batches(self):
        return SubmissionBatch.objects.filter(grant__college=self.request.institution).select_related(
            "grant__college", "grant__university"
        )


class Grants(InstitutionView):
    def get(self, request):
        here = request.institution.id
        rows = self.mine()
        return Response(
            [{**services.grant_item(g), "side": "college" if g.college_id == here else "university"} for g in rows]
        )


class Sent(InstitutionView):
    def get(self, request):
        return Response([services.batch_item(b) for b in self.own_batches().order_by("-created_at")])


class VersionInput(serializers.Serializer):
    version = serializers.IntegerField()
    reason = serializers.CharField(max_length=300, required=False, default="")


class Approve(InstitutionView):
    def post(self, request, pk):
        grant = found(self.mine(), pk)
        return Response(
            services.grant_item(services.approve(request.user, grant, valid(VersionInput, request.data)["version"]))
        )


class Revoke(InstitutionView):
    def post(self, request, pk):
        grant = found(self.mine(), pk)
        data = valid(VersionInput, request.data)
        return Response(services.grant_item(services.revoke(request.user, grant, data["version"], data["reason"])))


class BuildInput(serializers.Serializer):
    program = serializers.UUIDField()
    term = serializers.UUIDField()


class Batches(InstitutionView):
    def get(self, request, pk):
        grant = found(self.mine().filter(college=request.institution), pk)
        return Response([services.batch_item(b) for b in self.own_batches().filter(grant=grant)])

    def post(self, request, pk):
        grant = found(self.mine().filter(college=request.institution), pk)
        data = valid(BuildInput, request.data)
        program = found(request.institution.programs.all(), data["program"])
        term = found(Term.objects.filter(year__institution=request.institution).select_related("year"), data["term"])
        batch = services.build(request.user, grant, program, term)
        return Response(services.batch_item(batch), status=status.HTTP_201_CREATED)


class BatchDetail(InstitutionView):
    def get(self, request, pk):
        return Response(services.batch_item(found(self.own_batches(), pk)))


class BatchRow(InstitutionView):
    def delete(self, request, pk, row):
        batch = found(self.own_batches(), pk)
        services.remove_row(request.user, batch, found(batch.rows.all(), row))
        return Response(services.batch_item(batch))


class Submit(InstitutionView):
    def post(self, request, pk):
        return Response(services.batch_item(services.submit(request.user, found(self.own_batches(), pk))))


class ReviseInput(serializers.Serializer):
    corrections = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class Revise(InstitutionView):
    def post(self, request, pk):
        batch = found(self.own_batches(), pk)
        made = services.revise(request.user, batch, valid(ReviseInput, request.data)["corrections"])
        return Response(services.batch_item(made), status=status.HTTP_201_CREATED)


class Received(InstitutionView):
    def get(self, request):
        return Response([services.batch_item(b, True) for b in services.received(request.institution)])


class ReceivedDetail(InstitutionView):
    def get(self, request, pk):
        return Response(services.batch_item(found(services.received(request.institution), pk), True))


class DecideInput(serializers.Serializer):
    decision = serializers.ChoiceField(["accepted", "rejected"])
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class DecideRow(InstitutionView):
    def post(self, request, pk, row):
        batch = found(services.received(request.institution), pk)
        data = valid(DecideInput, request.data)
        changed = services.decide(request.user, batch, found(batch.rows.all(), row), data["decision"], data["reason"])
        return Response(services.batch_item(changed, True))
