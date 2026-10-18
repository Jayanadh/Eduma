from rest_framework import serializers


class CustomRoleInput(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    description = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    permissions = serializers.ListField(child=serializers.CharField(max_length=60), required=False, default=list)
    is_active = serializers.BooleanField(required=False)
    version = serializers.IntegerField(required=False)
