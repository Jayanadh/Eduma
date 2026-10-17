from rest_framework import serializers

from sites import content as page_content
from sites.models import SiteRevision
from sites.theme import BODY_FONTS, HEADING_FONTS, derive

HEX = r"^#[0-9A-Fa-f]{6}$"


def asset_url(asset_id) -> str:
    return f"/api/v1/public/assets/{asset_id}"


def theme_of(revision: SiteRevision) -> dict:
    """The stored theme plus the readable colours derived from it."""
    stored = {
        "primary_color": revision.primary_color,
        "secondary_color": revision.secondary_color,
        "heading_font": revision.heading_font,
        "body_font": revision.body_font,
    }
    return {**stored, **derive(revision.primary_color, revision.secondary_color)}


class SiteRevisionSerializer(serializers.ModelSerializer):
    theme = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    published_by_name = serializers.CharField(source="published_by.full_name", default=None, read_only=True)

    class Meta:
        model = SiteRevision
        fields = [
            "id",
            "number",
            "status",
            "version",
            "theme",
            "logo",
            "content",
            "created_at",
            "published_at",
            "published_by_name",
        ]
        read_only_fields = fields

    def get_theme(self, revision: SiteRevision) -> dict:
        return theme_of(revision)

    def get_logo(self, revision: SiteRevision) -> dict | None:
        return {"id": revision.logo_id, "url": asset_url(revision.logo_id)} if revision.logo_id else None


class RevisionListSerializer(serializers.ModelSerializer):
    published_by_name = serializers.CharField(source="published_by.full_name", default=None, read_only=True)

    class Meta:
        model = SiteRevision
        fields = ["id", "number", "status", "created_at", "published_at", "published_by_name"]
        read_only_fields = fields


class DraftInputSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    primary_color = serializers.RegexField(HEX, error_messages={"invalid": "Use a colour like #4B5AE4."})
    secondary_color = serializers.RegexField(HEX, error_messages={"invalid": "Use a colour like #FFD43B."})
    heading_font = serializers.ChoiceField(list(HEADING_FONTS))
    body_font = serializers.ChoiceField(list(BODY_FONTS))
    logo = serializers.UUIDField(allow_null=True)
    content = serializers.JSONField()

    def validate_primary_color(self, value: str) -> str:
        return value.upper()

    def validate_secondary_color(self, value: str) -> str:
        return value.upper()

    def validate_content(self, value) -> dict:
        return page_content.validate_content(value)


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField()


class RestoreSerializer(serializers.Serializer):
    """The draft's version, when there is a draft to replace."""

    version = serializers.IntegerField(required=False, allow_null=True, default=None)
