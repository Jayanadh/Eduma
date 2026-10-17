from rest_framework import serializers

from common.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", default=None, read_only=True)
    institution_name = serializers.CharField(source="institution.display_name", default=None, read_only=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "at", "actor_name", "institution_name", "action", "summary", "changes"]
        read_only_fields = fields
