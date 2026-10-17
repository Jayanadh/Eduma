import uuid

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.models import AuditEvent
from common.pagination import Pages
from common.serializers import AuditEventSerializer
from sites.permissions import PlatformAdmin


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Used by deploy checks and uptime monitors."""
    return Response({"status": "ok"})


class AuditEventList(ListAPIView):
    """The platform audit log. ?search= (summary or actor), ?action= (a prefix such as institution.), ?institution=."""

    serializer_class = AuditEventSerializer
    permission_classes = [PlatformAdmin]
    pagination_class = Pages

    def get_queryset(self):
        params = self.request.query_params
        queryset = AuditEvent.objects.select_related("actor", "institution")
        if institution := self.kwargs.get("institution_id") or record_id(params.get("institution")):
            queryset = queryset.filter(institution_id=institution)
        if prefix := params.get("action", "").strip():
            queryset = queryset.filter(action__startswith=prefix)
        if search := params.get("search", "").strip():
            queryset = queryset.filter(Q(summary__icontains=search) | Q(actor__full_name__icontains=search))
        return queryset


def record_id(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None
