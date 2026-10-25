"""Service cases for every kind of member, under service-cases/ (slice 10c; spec 09 `/service-cases`)."""

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.views import valid
from accounts.models import Membership
from accounts.permissions import active_membership, has_perm
from cases import services
from cases.models import ServiceCase
from configuration.gates import require_module


class CaseView(GenericAPIView):
    """Any active member of the institution: staff, students and guardians alike."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.site_kind != "institution" or active_membership(request.user, request.institution) is None:
            raise NotFound()
        require_module(request.institution, "services")

    def case(self, pk):
        return services.find(self.request.user, self.request.institution, pk)


class OpenInput(serializers.Serializer):
    case_type = serializers.ChoiceField(choices=ServiceCase.Type.choices)
    subject = serializers.CharField(max_length=150)
    description = serializers.CharField(max_length=4000)


class Cases(CaseView):
    def get(self, request):
        user, institution = request.user, request.institution
        rows = services.visible(user, institution, request.query_params.get("search", "").strip())
        if state := request.query_params.get("state"):
            rows = rows.filter(state=state)
        return Response([services.item(c, services.access(user, institution, c)) for c in rows[:200]])

    def post(self, request):
        data = valid(OpenInput, request.data)  # anything else sent (assignee, state, notes) is ignored
        made = services.open_case(request.user, request.institution, **data)
        return Response(services.item(made, "requester", detail=True), status=status.HTTP_201_CREATED)


class CaseDetail(CaseView):
    def get(self, request, pk):
        case, seen = self.case(pk)
        return Response(services.item(case, seen, detail=True))


class Notes(CaseView):
    def post(self, request, pk):
        case, _ = self.case(pk)
        services.add_note(
            request.user,
            request.institution,
            case,
            str(request.data.get("text", ""))[:4000],
            request.data.get("visibility") == "internal",
        )
        return Response(services.item(case, services.access(request.user, request.institution, case), detail=True))


class Assign(CaseView):
    def post(self, request, pk):
        case, _ = self.case(pk)
        assignee = Membership.objects.filter(institution=request.institution, pk=request.data.get("assignee")).first()
        if assignee is None:
            raise serializers.ValidationError({"assignee": ["Choose who handles it."]})
        done = services.assign(request.user, request.institution, case, assignee)
        return Response(services.item(done, services.access(request.user, request.institution, done), detail=True))


class Officers(CaseView):
    def get(self, request, pk):
        case, _ = self.case(pk)
        if not has_perm(request.user, request.institution, services.ASSIGN):
            raise NotFound()
        return Response(services.officers(request.institution, case.confidential))


class Resolve(CaseView):
    def post(self, request, pk):
        case, _ = self.case(pk)
        done = services.resolve(request.user, request.institution, case, str(request.data.get("text", ""))[:4000])
        return Response(services.item(done, "officer", detail=True))


class Appeals(CaseView):
    def post(self, request, pk):
        case, _ = self.case(pk)
        done = services.appeal(request.user, request.institution, case, str(request.data.get("reason", ""))[:4000])
        return Response(services.item(done, "requester", detail=True), status=status.HTTP_201_CREATED)
