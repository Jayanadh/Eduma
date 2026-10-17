from zoneinfo import available_timezones

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User, validate_username
from institutions.models import Institution, LifecycleStatus, validate_slug
from institutions.services import first_admin, readiness
from sites.hosts import institution_url

PROFILE_FIELDS = ["contact_email", "contact_phone", "address"]
EDITABLE_FIELDS = [
    "slug",
    "legal_name",
    "display_name",
    "category",
    "country_code",
    "timezone",
    "base_currency",
    *PROFILE_FIELDS,
    "board_affiliation_code",
    "udise_code",
    "aishe_code",
]


def django_errors(check, value):
    """Runs a Django validator and reports its message as a DRF field error."""
    try:
        return check(value)
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from error


class InstitutionFieldsMixin:
    def validate_slug(self, value: str) -> str:
        slug = django_errors(validate_slug, value)
        clash = Institution.objects.filter(slug=slug)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("This address is already taken.")
        return slug

    def validate_timezone(self, value: str) -> str:
        if value not in available_timezones():
            raise serializers.ValidationError("Choose a time zone such as Asia/Kolkata.")
        return value

    def validate_country_code(self, value: str) -> str:
        return value.upper()

    def validate_base_currency(self, value: str) -> str:
        return value.upper()


class AdminSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    mobile = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_username(self, value: str) -> str:
        username = django_errors(validate_username, value)
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError("This login ID is already in use.")
        return username

    def validate(self, attrs):
        candidate = User(username=attrs["username"], full_name=attrs["full_name"], email=attrs.get("email", ""))
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs


class InstitutionCreateSerializer(InstitutionFieldsMixin, serializers.ModelSerializer):
    admin = AdminSerializer()

    class Meta:
        model = Institution
        fields = [*EDITABLE_FIELDS, "admin"]
        extra_kwargs = {"slug": {"validators": []}}  # checked in validate_slug, with a friendlier message


def admin_summary(institution: Institution) -> dict | None:
    admin = first_admin(institution)
    if admin is None:
        return None
    return {
        "id": admin.id,
        "username": admin.username,
        "full_name": admin.full_name,
        "must_change_password": admin.must_change_password,
        "last_login": admin.last_login,
    }


class InstitutionSerializer(InstitutionFieldsMixin, serializers.ModelSerializer):
    """An institution as the platform admin sees it. PATCH takes `version` and any editable field."""

    url = serializers.SerializerMethodField()
    readiness = serializers.SerializerMethodField()
    admin = serializers.SerializerMethodField()
    version = serializers.IntegerField()

    class Meta:
        model = Institution
        fields = [
            "id",
            *EDITABLE_FIELDS,
            "url",
            "lifecycle_status",
            "status_reason",
            "activated_at",
            "created_at",
            "version",
            "readiness",
            "admin",
        ]
        read_only_fields = ["id", "lifecycle_status", "status_reason", "activated_at", "created_at"]
        extra_kwargs = {"slug": {"validators": []}}

    def get_url(self, institution: Institution) -> str:
        return institution_url(institution.slug)

    def get_readiness(self, institution: Institution) -> list[dict]:
        return readiness(institution)

    def get_admin(self, institution: Institution) -> dict | None:
        return admin_summary(institution)


class OwnInstitutionSerializer(InstitutionSerializer):
    """What an institution's own members see of it: everything but the admin summary."""

    class Meta(InstitutionSerializer.Meta):
        fields = [name for name in InstitutionSerializer.Meta.fields if name != "admin"]


class InstitutionProfileSerializer(serializers.ModelSerializer):
    """The fields an institution's own admin may change."""

    version = serializers.IntegerField()

    class Meta:
        model = Institution
        fields = [*PROFILE_FIELDS, "version"]


class InstitutionListSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    ready = serializers.SerializerMethodField()

    class Meta:
        model = Institution
        fields = ["id", "display_name", "slug", "url", "category", "lifecycle_status", "created_at", "ready"]

    def get_url(self, institution: Institution) -> str:
        return institution_url(institution.slug)

    def get_ready(self, institution: Institution) -> bool:
        return bool(institution.admin_ready and institution.site_published and institution.contacts)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False)


class TransitionSerializer(serializers.Serializer):
    to = serializers.ChoiceField(LifecycleStatus.choices)
    reason = serializers.CharField(max_length=500, allow_blank=True)
    override_reason = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    version = serializers.IntegerField()
