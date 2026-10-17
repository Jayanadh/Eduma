"""What visitors see at / on any host: the Eduma page on the main host, or an institution's page on its own host.
Only published content is public; while an institution is being set up its page shows its name, look and "opening
soon"; a suspended one shows that it is unavailable; an archived or unknown one does not exist."""

import copy

from django.http import FileResponse, Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from institutions.models import SIGN_IN_STATES, LifecycleStatus
from sites.eduma_content import eduma_content
from sites.models import BrandAsset, SiteRevision
from sites.serializers import asset_url, theme_of
from sites.theme import DEFAULT_THEME, derive

EDUMA_LOGO = "/eduma-logo.png"  # bundled with the frontend


def with_urls(content: dict) -> dict:
    """A copy of the content where every image also carries the URL it is served from (None for an empty slot)."""
    content = copy.deepcopy(content)

    def walk(value):
        if isinstance(value, dict):
            if "asset" in value:
                value["url"] = asset_url(value["asset"]) if value["asset"] else None
            for inner in value.values():
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(content)
    return content


def _institution_payload(institution) -> dict:
    revisions = institution.site_revisions
    published = revisions.filter(status=SiteRevision.Status.PUBLISHED).first()
    profile = {
        "slug": institution.slug,
        "display_name": institution.display_name,
        "category": institution.category,
        "contact_email": institution.contact_email,
        "contact_phone": institution.contact_phone,
        "address": institution.address,
    }
    if institution.lifecycle_status == LifecycleStatus.ACTIVE and published is not None:
        return {
            "kind": "institution", "mode": "full", "institution": profile, "theme": theme_of(published),
            "content": with_urls(published.content),
            "logo_url": asset_url(published.logo_id) if published.logo_id else None,
        }
    # Opening soon: the institution's look and the hero title only, never unpublished page content.
    look = published or revisions.filter(status=SiteRevision.Status.DRAFT).first()
    hero = (look.content.get("sections") or [{}])[0] if look else {}
    title = hero.get("title") or institution.display_name
    return {
        "kind": "institution", "mode": "opening_soon", "institution": profile,
        "theme": theme_of(look) if look else {**DEFAULT_THEME, **derive(DEFAULT_THEME["primary_color"],
                                                                         DEFAULT_THEME["secondary_color"])},
        "content": {"sections": [{"id": "hero", "type": "hero", "visible": True, "title": title}]},
        "logo_url": asset_url(look.logo_id) if look and look.logo_id else None,
    }


class PublicSiteView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if request.site_kind == "platform":
            theme = {**DEFAULT_THEME, **derive(DEFAULT_THEME["primary_color"], DEFAULT_THEME["secondary_color"])}
            return Response({"kind": "platform", "theme": theme, "content": with_urls(eduma_content()),
                             "logo_url": EDUMA_LOGO})
        institution = request.institution
        if institution is None or institution.lifecycle_status == LifecycleStatus.ARCHIVED:
            raise Http404
        if institution.lifecycle_status == LifecycleStatus.SUSPENDED:
            return Response({"kind": "institution", "mode": "unavailable",
                             "institution": {"display_name": institution.display_name}})
        return Response(_institution_payload(institution))


def public_asset(request, asset_id):
    """A brand image, while its institution is being set up or is active. Images never change, so caches keep them."""
    asset = BrandAsset.objects.select_related("institution").filter(pk=asset_id).first()
    if asset is None or asset.institution.lifecycle_status not in SIGN_IN_STATES:
        raise Http404
    response = FileResponse(asset.file.open("rb"), content_type=asset.content_type)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
