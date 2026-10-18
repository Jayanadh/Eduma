"""What anyone may see of an institution's admissions: its published, unclosed cycles (slice 4a spec §5). Never seat
counts, applicants or anything unpublished."""

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from accounts.permissions import today_for
from admissions.models import AdmissionCycle
from configuration.gates import module_on
from institutions.models import SIGN_IN_STATES


def public_cycle(cycle: AdmissionCycle) -> dict:
    return {
        "id": str(cycle.id),
        "name": cycle.name,
        "academic_year": cycle.academic_year,
        "opens_on": cycle.opens_on,
        "closes_on": cycle.closes_on,
        "instructions": cycle.instructions,
        "places": [
            {"id": str(place.id), "label": place.label, "campus_name": place.campus.name if place.campus_id else None}
            for place in cycle.places.select_related("campus")
        ],
        "documents": list(cycle.documents.values("code", "label", "required")),
    }


class PublicThrottle(SimpleRateThrottle):
    """Per address: public reads are rate limited (spec pack 09 §4.7)."""

    scope = "public"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_admissions(request):
    if request.site_kind != "institution":
        raise NotFound()
    institution = request.institution
    if institution.lifecycle_status not in SIGN_IN_STATES or not module_on(institution, "admissions"):
        return Response({"open": False, "cycles": []})
    today = today_for(institution)
    cycles = institution.cycles.filter(status=AdmissionCycle.Status.PUBLISHED, closes_on__gte=today)
    return Response(
        {
            "open": any(cycle.opens_on <= today for cycle in cycles),
            "cycles": [public_cycle(cycle) for cycle in cycles.order_by("opens_on")],
        }
    )
