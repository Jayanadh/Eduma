from django.contrib.auth import password_validation
from rest_framework import serializers

from accounts.models import User
from accounts.permissions import active_membership, in_effect, perms_anywhere, today_for


class MeSerializer(serializers.ModelSerializer):
    """The signed-in user, with their membership in the host's institution (none on the platform host)."""

    membership = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "is_platform_admin", "must_change_password", "membership"]
        read_only_fields = fields

    def get_membership(self, user: User) -> dict | None:
        request = self.context["request"]
        membership = active_membership(user, request.institution) if request.site_kind == "institution" else None
        if membership is None:
            return None
        institution = request.institution
        rows = membership.assignments.select_related("custom_role", "campus", "department")
        roles = in_effect(rows, today_for(institution))
        restricted = institution.lifecycle_status == "restricted"
        return {
            "kind": membership.kind,
            "roles": [{"label": row.role_label, "scope_label": row.scope_label} for row in roles],
            "permissions": sorted(perms_anywhere(user, institution)),
            "restricted": restricted,
            "status_reason": institution.status_reason if restricted else "",
        }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def validate(self, attrs):
        # Whoever set a first password still knows it, so keeping it is not a change.
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError({"new_password": ["Choose a password different from your current one."]})
        return attrs
