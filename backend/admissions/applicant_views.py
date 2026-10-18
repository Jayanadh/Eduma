"""An applicant's own applications, on the institution's address (slice 4a spec §5). Anything not theirs is 404."""

import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import active_membership
from admissions import applications as services
from admissions import documents
from admissions.applications import expire_if_due
from admissions.serializers import ApplicationInput, StartInput, applicant_item
from common.pagination import Pages
from configuration.gates import require_module
from configuration.serializers import VersionInput


class ApplicantView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.site_kind != "institution" or active_membership(request.user, request.institution) is None:
            raise NotFound()
        require_module(request.institution, "admissions")

    def own(self):
        return self.request.institution.applications.filter(owner=self.request.user).select_related(
            "cycle", "place__campus", "institution"
        )

    def application(self):
        found = self.own().filter(pk=self.kwargs["pk"]).first()
        if found is None:
            raise NotFound()
        return expire_if_due(found)

    def data(self, serializer_class):
        found = serializer_class(data=self.request.data, context={"institution": self.request.institution})
        found.is_valid(raise_exception=True)
        return found.validated_data


class ApplicationList(ApplicantView):
    pagination_class = Pages

    def get(self, request):
        page = self.paginate_queryset(self.own())
        return self.get_paginated_response([applicant_item(expire_if_due(row)) for row in page])

    def post(self, request):
        values = self.data(StartInput)
        try:
            key = (
                uuid.UUID(request.headers.get("Idempotency-Key", ""))
                if request.headers.get("Idempotency-Key")
                else None
            )
        except ValueError:
            key = None
        found = services.start(request.user, request.institution, values["cycle"], values["place"], key)
        return Response(applicant_item(found), status=status.HTTP_201_CREATED)


class ApplicationDetail(ApplicantView):
    def get(self, request, pk):
        return Response(applicant_item(self.application()))

    def patch(self, request, pk):
        found = self.application()
        values = self.data(ApplicationInput)
        version = values.pop("version")
        return Response(applicant_item(services.edit(request.user, found, version, values)))


class Step(ApplicantView):
    action_name = ""

    def post(self, request, pk):
        found = self.application()
        version = self.data(VersionInput)["version"]
        done = getattr(services, self.action_name)(request.user, found, version)
        return Response(applicant_item(done))


class Submit(Step):
    action_name = "submit"


class Withdraw(Step):
    action_name = "withdraw"


class Accept(Step):
    action_name = "accept"


class Documents(ApplicantView):
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        found = self.application()
        documents.upload(request.user, found, request.data.get("requirement", ""), request.FILES.get("file"))
        found.refresh_from_db()
        return Response(applicant_item(found), status=status.HTTP_201_CREATED)


class DocumentFile(ApplicantView):
    def get(self, request, pk, doc):
        found = self.application().documents.filter(pk=doc).first()
        if found is None:
            raise NotFound()
        return documents.download_response(found)
