from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import Pages
from institutions.models import Institution
from sites import services
from sites.permissions import member_with
from sites.serializers import (
    DraftInputSerializer,
    RestoreSerializer,
    RevisionListSerializer,
    SiteRevisionSerializer,
    VersionSerializer,
    asset_url,
)


class InstitutionScopedView(APIView):
    """Under /api/v1/institution/site/ on an institution's own host, for its members with the brand permission."""

    permission_classes = [member_with("institution_brand.update")]

    def institution(self) -> Institution:
        return self.request.institution


def revision_response(revision):
    return Response(SiteRevisionSerializer(revision).data)


class DraftView(InstitutionScopedView):
    def get(self, request, **kwargs):
        return revision_response(services.get_or_create_draft(self.institution(), request.user))

    def put(self, request, **kwargs):
        serializer = DraftInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return revision_response(services.save_draft(self.institution(), request.user, data["version"], data))


class PublishView(InstitutionScopedView):
    def post(self, request, **kwargs):
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return revision_response(
            services.publish(self.institution(), request.user, serializer.validated_data["version"])
        )


class RevisionsView(InstitutionScopedView, ListAPIView):
    serializer_class = RevisionListSerializer
    pagination_class = Pages

    def get_queryset(self):
        return self.institution().site_revisions.select_related("published_by")


class RestoreView(InstitutionScopedView):
    def post(self, request, revision_id, **kwargs):
        serializer = RestoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = serializer.validated_data["version"]
        return revision_response(services.restore(self.institution(), request.user, revision_id, version))


class AssetsView(InstitutionScopedView):
    parser_classes = [MultiPartParser]

    def post(self, request, **kwargs):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Choose an image to upload."]})
        asset = services.store_asset(self.institution(), request.user, upload)
        body = {"id": asset.id, "url": asset_url(asset.id), "width": asset.width, "height": asset.height}
        return Response(body, status=status.HTTP_201_CREATED)
