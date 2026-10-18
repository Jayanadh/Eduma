import uuid

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import Pages
from institutions import services
from institutions.models import Institution, validate_slug
from institutions.modules import MODULES
from institutions.serializers import (
    InstitutionCreateSerializer,
    InstitutionListSerializer,
    InstitutionProfileSerializer,
    InstitutionSerializer,
    OwnInstitutionSerializer,
    PasswordSerializer,
    TransitionSerializer,
)
from sites.permissions import PlatformAdmin, member_with

UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class PlatformInstitutionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """The platform admin's institution directory, onboarding and per-institution actions."""

    permission_classes = [PlatformAdmin]
    pagination_class = Pages
    lookup_value_regex = UUID_RE
    queryset = Institution.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return InstitutionListSerializer
        if self.action == "create":
            return InstitutionCreateSerializer
        return InstitutionSerializer

    def get_queryset(self):
        queryset = Institution.objects.order_by("-created_at")
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if len(search := params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(
                Q(display_name__icontains=search) | Q(legal_name__icontains=search) | Q(slug__icontains=search)
            )
        if category := params.get("category"):
            queryset = queryset.filter(category=category)
        if state := params.get("status"):
            queryset = queryset.filter(lifecycle_status=state)
        return services.with_readiness(queryset)

    def create(self, request, *args, **kwargs):
        try:
            key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        except ValueError:
            raise ParseError("Send an Idempotency-Key header with a UUID.") from None
        digest = services.request_digest(request.data)
        institution, created = services.replayed(key, digest), False
        if institution is None:
            serializer = InstitutionCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            institution, created = services.create_institution(request.user, serializer.validated_data, key, digest)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(InstitutionSerializer(institution).data, status=code)

    def partial_update(self, request, *args, **kwargs):
        institution = self.get_object()
        serializer = InstitutionSerializer(institution, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        version = changes.pop("version", None)
        updated = services.update_institution(institution.pk, request.user, version, changes)
        return Response(InstitutionSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        institution = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.transition(institution.pk, request.user, **serializer.validated_data)
        return Response(InstitutionSerializer(updated).data)

    @action(detail=False, methods=["get"], url_path="slug-check")
    def slug_check(self, request):
        try:
            slug = validate_slug(request.query_params.get("slug", ""))
        except DjangoValidationError as error:
            return Response({"available": False, "reason": error.messages[0]})
        if Institution.objects.filter(slug=slug).exists():
            return Response({"available": False, "reason": "This address is already taken."})
        return Response({"available": True, "reason": ""})

    @action(detail=True, methods=["post"], url_path="admin-password")
    def admin_password(self, request, pk=None):
        institution = self.get_object()
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["password"]
        admin = services.first_admin(institution)
        if admin is not None:
            try:
                password_validation.validate_password(password, admin)
            except DjangoValidationError as error:
                raise ValidationError({"password": error.messages}) from error
        services.reset_admin_password(institution, request.user, password)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnInstitutionView(APIView):
    """An institution's own profile, on its own host. Its admin may change the contact details."""

    def get_permissions(self):
        perm = "institution.read" if self.request.method == "GET" else "institution_profile.update"
        return [member_with(perm)()]

    def get(self, request):
        return Response(OwnInstitutionSerializer(request.institution).data)

    def patch(self, request):
        serializer = InstitutionProfileSerializer(request.institution, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        version = changes.pop("version", None)
        updated = services.update_institution(request.institution.pk, request.user, version, changes)
        return Response(OwnInstitutionSerializer(updated).data)


@api_view(["GET"])
@permission_classes([PlatformAdmin])
def platform_overview(request):
    return Response(services.overview())


@api_view(["GET"])
@permission_classes([PlatformAdmin])
def module_catalogue(request):
    """Every module a plan can include, for the onboarding wizard and an institution's Modules tab."""
    return Response(
        [
            {
                "key": module.key,
                "label": module.label,
                "group": module.group,
                "depends_on": list(module.depends_on),
                "default_for": sorted(module.default_for),
                "available": module.available,
            }
            for module in MODULES.values()
        ]
    )
