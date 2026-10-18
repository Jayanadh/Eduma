"""Applications for staff: list, detail, review steps, offers, documents and notes (slice 4a spec §5)."""

from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.role_views import holds_any
from admissions import documents, review
from admissions.applications import expire_if_due
from admissions.serializers import staff_item, staff_list_item
from common.pagination import Pages
from configuration.gates import require_module


class Version(serializers.Serializer):
    version = serializers.IntegerField()


class Message(Version):
    message = serializers.CharField(max_length=1000, allow_blank=True)


class Reason(Version):
    reason = serializers.CharField(max_length=500, allow_blank=True)


class Offer(Version):
    expires_on = serializers.DateField()


class DocumentReview(Version):
    note = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")


class NoteInput(serializers.Serializer):
    text = serializers.CharField(max_length=2000, allow_blank=True)


class StaffView(GenericAPIView):
    permission_classes = [holds_any("application.review", "admission.approve")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "admissions")

    def visible(self):
        return review.visible(self.request.user, self.request.institution).select_related(
            "cycle", "place__campus", "institution", "owner", "decided_by"
        )

    def application(self):
        found = self.visible().filter(pk=self.kwargs["pk"]).first()
        if found is None:
            raise NotFound()
        return expire_if_due(found)

    def data(self, serializer_class):
        found = serializer_class(data=self.request.data)
        found.is_valid(raise_exception=True)
        return found.validated_data

    def answer(self, application, code=status.HTTP_200_OK) -> Response:
        application.refresh_from_db()
        return Response(staff_item(application, self.request.user), status=code)


class ApplicationList(StaffView):
    pagination_class = Pages

    def get(self, request):
        queryset = self.visible()
        params = request.query_params
        for name in ("cycle", "stage", "place"):
            if value := params.get(name):
                queryset = queryset.filter(**{f"{name}_id" if name != "stage" else name: value})
        if len(search := params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(
                Q(number__icontains=search) | Q(learner_name__icontains=search) | Q(guardian_name__icontains=search)
            )
        page = self.paginate_queryset(queryset.order_by("-submitted_at"))
        return self.get_paginated_response([staff_list_item(expire_if_due(row)) for row in page])


class ApplicationDetail(StaffView):
    def get(self, request, pk):
        return Response(staff_item(self.application(), request.user))


class StartReview(StaffView):
    def post(self, request, pk):
        found = self.application()
        return self.answer(review.start_review(request.user, found, self.data(Version)["version"]))


class RequestInformation(StaffView):
    def post(self, request, pk):
        found = self.application()
        values = self.data(Message)
        return self.answer(review.request_information(request.user, found, values["version"], values["message"]))


class Eligible(StaffView):
    def post(self, request, pk):
        found = self.application()
        return self.answer(review.mark_eligible(request.user, found, self.data(Version)["version"]))


class Reject(StaffView):
    def post(self, request, pk):
        found = self.application()
        values = self.data(Reason)
        return self.answer(review.reject(request.user, found, values["version"], values["reason"]))


class MakeOffer(StaffView):
    def post(self, request, pk):
        found = self.application()
        values = self.data(Offer)
        return self.answer(review.offer(request.user, found, values["version"], values["expires_on"]))


class Notes(StaffView):
    def post(self, request, pk):
        found = self.application()
        review.add_note(request.user, found, self.data(NoteInput)["text"])
        return self.answer(found, status.HTTP_201_CREATED)


class DocumentView(StaffView):
    def document(self):
        found = self.application().documents.filter(pk=self.kwargs["doc"]).select_related("requirement").first()
        if found is None:
            raise NotFound()
        return found

    def get(self, request, pk, doc):
        return documents.download_response(self.document())


class VerifyDocument(DocumentView):
    def post(self, request, pk, doc):
        found = self.document()
        values = self.data(DocumentReview)
        review.review_document(request.user, found, values["version"], True, values["note"])
        return self.answer(found.application)


class RejectDocument(DocumentView):
    def post(self, request, pk, doc):
        found = self.document()
        values = self.data(DocumentReview)
        review.review_document(request.user, found, values["version"], False, values["note"])
        return self.answer(found.application)
