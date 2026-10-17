"""Draft, save, publish and restore an institution's theme and public page. Each runs in one transaction holding a lock
on the institution's row, so two editors of the same institution take turns."""

from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common import audit
from common.exceptions import Problem
from institutions.models import Institution
from sites.content import referenced_assets
from sites.models import BrandAsset, SiteRevision
from sites.starter import starter_content
from sites.theme import DEFAULT_THEME

Status = SiteRevision.Status
THEME_FIELDS = ("primary_color", "secondary_color", "heading_font", "body_font")


def _lock(institution: Institution) -> Institution:
    return Institution.objects.select_for_update().get(pk=institution.pk)


def _draft_gone() -> Problem:
    return Problem(
        409, "version_conflict", "This draft was published or replaced by someone else. Reload to continue.",
        current_version=None,
    )


def _create_draft(institution: Institution, actor) -> SiteRevision:
    revisions = institution.site_revisions
    number = (revisions.aggregate(Max("number"))["number__max"] or 0) + 1
    published = revisions.filter(status=Status.PUBLISHED).first()
    if published is not None:
        fields = {name: getattr(published, name) for name in (*THEME_FIELDS, "logo", "content")}
    else:
        fields = {**DEFAULT_THEME, "content": starter_content(institution.display_name, institution.category)}
    return SiteRevision.objects.create(institution=institution, number=number, created_by=actor, **fields)


def get_or_create_draft(institution: Institution, actor) -> SiteRevision:
    with transaction.atomic():
        institution = _lock(institution)
        draft = institution.site_revisions.filter(status=Status.DRAFT).first()
        return draft or _create_draft(institution, actor)


def _check_assets(institution: Institution, logo_id, content: dict) -> None:
    owned = set(map(str, BrandAsset.objects.filter(institution=institution).values_list("id", flat=True)))
    if logo_id is not None and str(logo_id) not in owned:
        raise ValidationError({"logo": ["Upload the logo for this institution first."]})
    if referenced_assets(content) - owned:
        raise ValidationError({"content": ["An image on the page does not belong to this institution."]})


def save_draft(institution: Institution, actor, version: int, data: dict) -> SiteRevision:
    """`data` holds the theme fields, `logo` (an asset id or None) and validated `content`."""
    with transaction.atomic():
        institution = _lock(institution)
        draft = institution.site_revisions.filter(status=Status.DRAFT).first()
        if draft is None:
            raise _draft_gone()
        draft.check_version(version)
        _check_assets(institution, data["logo"], data["content"])
        for name in THEME_FIELDS:
            setattr(draft, name, data[name])
        draft.logo_id = data["logo"]
        draft.content = data["content"]
        draft.save()
        return draft


def publish(institution: Institution, actor, version: int) -> SiteRevision:
    with transaction.atomic():
        institution = _lock(institution)
        draft = institution.site_revisions.filter(status=Status.DRAFT).first()
        if draft is None:
            raise _draft_gone()
        draft.check_version(version)
        institution.site_revisions.filter(status=Status.PUBLISHED).update(status=Status.SUPERSEDED)
        draft.status = Status.PUBLISHED
        draft.published_by = actor
        draft.published_at = timezone.now()
        draft.save()
        audit.log(actor, "site.published", draft, f"Published version {draft.number} of {institution}'s page",
                  institution=institution)
        return draft


def restore(institution: Institution, actor, revision_id) -> SiteRevision:
    """Copies an earlier revision's theme, logo and content into the draft; publishing it is a separate step."""
    with transaction.atomic():
        institution = _lock(institution)
        source = institution.site_revisions.filter(pk=revision_id).first()
        if source is None:
            raise Http404
        draft = institution.site_revisions.filter(status=Status.DRAFT).first() or _create_draft(institution, actor)
        for name in (*THEME_FIELDS, "logo", "content"):
            setattr(draft, name, getattr(source, name))
        draft.save()
        audit.log(actor, "site.restored", draft, f"Restored version {source.number} of {institution}'s page into the draft",
                  institution=institution)
        return draft
