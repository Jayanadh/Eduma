"""Enquiries: the public question form, and the admissions office's list and actions."""

from django.db.models import Count, Q
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from accounts.role_views import holds_any
from admissions import enquiries
from admissions.models import Enquiry, FollowUp
from common.pagination import Pages
from configuration.gates import require_module
from configuration.serializers import VersionInput


class EnquiryThrottle(SimpleRateThrottle):
    """Per visitor address: a public form must not become a way to flood the office."""

    scope = "enquiry"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class AskInput(serializers.Serializer):
    contact_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False, default="")
    email = serializers.EmailField(allow_blank=True, required=False, default="")
    learner_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    learner_date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    place = serializers.UUIDField(required=False, allow_null=True, default=None)
    message = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")


class PublicAskInput(AskInput):
    website = serializers.CharField(allow_blank=True, required=False, default="")  # a field only bots fill in


class StaffAskInput(AskInput):
    source = serializers.ChoiceField(Enquiry.Source.choices)


class EnquiryUpdate(serializers.Serializer):
    version = serializers.IntegerField()
    assigned_to = serializers.UUIDField(required=False, allow_null=True)
    next_follow_up_on = serializers.DateField(required=False, allow_null=True)
    place = serializers.UUIDField(required=False, allow_null=True)
    contact_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    learner_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    learner_date_of_birth = serializers.DateField(required=False, allow_null=True)


class FollowUpInput(serializers.Serializer):
    how = serializers.ChoiceField(FollowUp.How.choices)
    note = serializers.CharField(max_length=1000, allow_blank=True)
    next_follow_up_on = serializers.DateField(required=False, allow_null=True, default=None)


class ConvertInput(serializers.Serializer):
    version = serializers.IntegerField()
    application_number = serializers.CharField(max_length=20)


class CloseInput(serializers.Serializer):
    version = serializers.IntegerField()
    reason = serializers.CharField(max_length=500, allow_blank=True)


def _valid(serializer_class, data) -> dict:
    found = serializer_class(data=data)
    found.is_valid(raise_exception=True)
    return dict(found.validated_data)


class PublicEnquiry(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EnquiryThrottle]

    def post(self, request):
        if request.site_kind != "institution":
            raise NotFound()
        require_module(request.institution, "admissions")
        data = _valid(PublicAskInput, request.data)
        if data.pop("website"):
            return Response({"number": ""}, status=status.HTTP_201_CREATED)  # look accepted; store nothing
        enquiry = enquiries.create(request.institution, data, Enquiry.Source.WEBSITE)
        return Response({"number": enquiry.number}, status=status.HTTP_201_CREATED)


class EnquiryView(GenericAPIView):
    permission_classes = [holds_any(enquiries.MANAGE)]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "admissions")

    def enquiry(self) -> Enquiry:
        found = enquiries.visible(self.request.user, self.request.institution).filter(pk=self.kwargs["pk"]).first()
        if found is None:
            raise NotFound()
        return found

    def done(self, enquiry: Enquiry, code=status.HTTP_200_OK) -> Response:
        found = enquiries.visible(self.request.user, self.request.institution).get(pk=enquiry.pk)
        return Response(enquiries.enquiry_item(found, full=True), status=code)


class EnquiryList(EnquiryView):
    pagination_class = Pages

    def get(self, request):
        everything = enquiries.visible(request.user, request.institution)
        queryset = everything
        params = request.query_params
        if len(search := params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(
                Q(number__icontains=search)
                | Q(contact_name__icontains=search)
                | Q(learner_name__icontains=search)
                | Q(phone__icontains=search)
            )
        if state := params.get("status"):
            queryset = queryset.filter(status=state)
        if source := params.get("source"):
            queryset = queryset.filter(source=source)
        if params.get("assigned") == "me":
            queryset = queryset.filter(assigned_to=request.user)
        if params.get("due"):
            queryset = enquiries.due(queryset, request.institution)
        page = self.paginate_queryset(queryset.order_by("-created_at"))
        response = self.get_paginated_response([enquiries.enquiry_item(row) for row in page])

        def counts(field):
            return {row[field]: row["n"] for row in everything.order_by().values(field).annotate(n=Count("id"))}

        response.data["summary"] = {"status": counts("status"), "source": counts("source")}
        return response

    def post(self, request):
        data = _valid(StaffAskInput, request.data)
        source = data.pop("source")
        enquiry = enquiries.create(request.institution, data, source, actor=request.user)
        return self.done(enquiry, status.HTTP_201_CREATED)


class EnquiryDetail(EnquiryView):
    def get(self, request, pk):
        return Response(enquiries.enquiry_item(self.enquiry(), full=True))

    def patch(self, request, pk):
        found = self.enquiry()
        data = _valid(EnquiryUpdate, request.data)
        return self.done(enquiries.update(request.user, found, data.pop("version"), data))


class FollowUps(EnquiryView):
    def post(self, request, pk):
        found = self.enquiry()
        return self.done(enquiries.add_follow_up(request.user, found, _valid(FollowUpInput, request.data)), 201)


class Convert(EnquiryView):
    def post(self, request, pk):
        found = self.enquiry()
        data = _valid(ConvertInput, request.data)
        return self.done(enquiries.convert(request.user, found, data["version"], data["application_number"]))


class Close(EnquiryView):
    def post(self, request, pk):
        found = self.enquiry()
        data = _valid(CloseInput, request.data)
        return self.done(enquiries.close(request.user, found, data["version"], data["reason"]))


class Reopen(EnquiryView):
    def post(self, request, pk):
        found = self.enquiry()
        return self.done(enquiries.reopen(request.user, found, _valid(VersionInput, request.data)["version"]))
