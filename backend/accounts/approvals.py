"""What is waiting for the caller's decision: role requests they may approve and setting changes they may publish
(slice 3 spec §4). Most members get two empty lists."""

from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.models import RoleAssignment
from accounts.staff import can_decide
from configuration.models import SettingRevision
from configuration.registry import definition
from configuration.serializers import revision_item
from sites.permissions import member_with


class Approvals(GenericAPIView):
    permission_classes = [member_with("institution.read")]

    def get(self, request):
        institution = request.institution
        waiting = RoleAssignment.objects.filter(institution=institution, status=RoleAssignment.Status.PENDING)
        rows = waiting.select_related(
            "membership__user", "created_by", "custom_role", "campus", "department", "institution"
        )
        roles = [
            {
                "staff_id": str(row.membership_id),
                "assignment_id": str(row.id),
                "person": row.membership.user.full_name,
                "role_label": row.role_label,
                "scope_label": row.scope_label,
                "requested_by_name": row.created_by.full_name if row.created_by else None,
                "requested_at": row.created_at,
            }
            for row in rows.order_by("created_at")
            if can_decide(request.user, row)
        ]
        pending = institution.settings.filter(status=SettingRevision.Status.PENDING).select_related(
            "institution", "created_by", "submitted_by", "approved_by"
        )
        settings = []
        for revision in pending:
            item = revision_item(revision, request.user)
            if item["can_approve"]:
                settings.append(
                    {
                        "key": revision.key,
                        "label": definition(revision.key).label,
                        "revision_id": item["id"],
                        "submitted_by_name": item["submitted_by_name"],
                        "description": item["description"],
                    }
                )
        return Response({"roles": roles, "settings": settings})
