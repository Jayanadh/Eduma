from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from institutions.models import Institution
from sites import services
from sites.permissions import PlatformAdmin, member_with
from sites.serializers import (
    DraftInputSerializer,
    RevisionListSerializer,
    SiteRevisionSerializer,
    VersionSerializer,
    asset_url,
)


class InstitutionScopedView(APIView):
    """Served twice: under /api/v1/platform/institutions/<id>/ for platform admins (any institution), and under
    /api/v1/institution/ on an institution's own host for its members with the brand permission."""

    def get_permissions(self):
        if "institution_id" in self.kwargs:
            return [PlatformAdmin()]
        return [member_with("institution_brand.update")()]

    def institution(self) -> Institution:
        if "institution_id" in self.kwargs:
            return get_object_or_404(Institution, pk=self.kwargs["institution_id"])
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
        return revision_response(services.publish(self.institution(), request.user, serializer.validated_data["version"]))


class RevisionsView(InstitutionScopedView):
    def get(self, request, **kwargs):
        revisions = self.institution().site_revisions.select_related("published_by")
        return Response(RevisionListSerializer(revisions, many=True).data)


class RestoreView(InstitutionScopedView):
    def post(self, request, revision_id, **kwargs):
        return revision_response(services.restore(self.institution(), request.user, revision_id))


class AssetsView(InstitutionScopedView):
    parser_classes = [MultiPartParser]

    def post(self, request, **kwargs):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Choose an image to upload."]})
        asset = services.store_asset(self.institution(), request.user, upload)
        body = {"id": asset.id, "url": asset_url(asset.id), "width": asset.width, "height": asset.height}
        return Response(body, status=status.HTTP_201_CREATED)
