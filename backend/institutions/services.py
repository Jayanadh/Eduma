import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q

from accounts.models import Membership, Role, User
from common import audit
from common.exceptions import IdempotencyMismatch, InvalidTransition
from institutions.models import Institution, LifecycleStatus
from sites.models import SiteRevision
from sites.services import get_or_create_draft

READINESS = (
    ("admin_ready", "Institution Admin has signed in and changed their first password"),
    ("site_published", "Public page is published"),
    ("contacts", "Contact email and phone are filled in"),
)


def _admins(institution_ref):
    return Membership.objects.filter(
        institution=institution_ref, role=Role.INSTITUTION_ADMIN, status=Membership.Status.ACTIVE, user__is_active=True
    )


def with_readiness(queryset):
    """Annotates each institution with one boolean per readiness check (see READINESS)."""
    return queryset.annotate(
        admin_ready=Exists(_admins(OuterRef("pk")).filter(user__last_login__isnull=False,
                                                           user__must_change_password=False)),
        site_published=Exists(SiteRevision.objects.filter(institution=OuterRef("pk"), status="published")),
        contacts=ExpressionWrapper(~Q(contact_email="") & ~Q(contact_phone=""), output_field=BooleanField()),
    )


def readiness(institution: Institution) -> list[dict]:
    checked = with_readiness(Institution.objects.filter(pk=institution.pk)).get()
    return [{"code": code, "label": label, "done": getattr(checked, code)} for code, label in READINESS]


def first_admin(institution: Institution) -> User | None:
    membership = _admins(institution).select_related("user").order_by("created_at").first()
    return membership.user if membership else None


def request_digest(data: dict) -> str:
    """A fingerprint of an onboarding request, without the first password (never stored, even hashed this way)."""
    body = json.loads(json.dumps(data, default=str))
    body.get("admin", {}).pop("password", None)
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def replayed(key, digest: str) -> Institution | None:
    """The institution an earlier request with this key created, if any. The same key with other details is refused."""
    existing = Institution.objects.filter(creation_key=key).first()
    if existing is not None and existing.creation_hash != digest:
        raise IdempotencyMismatch()
    return existing


def create_institution(actor, data: dict, key, digest: str) -> tuple[Institution, bool]:
    """Creates the institution (in setup), its admin login with a first password, the admin's membership and a starter
    draft page, all or nothing. Returns (institution, created); a retry with the same key returns the first one."""
    fields = dict(data)
    admin = fields.pop("admin")
    try:
        with transaction.atomic():
            institution = Institution.objects.create(
                **fields, lifecycle_status=LifecycleStatus.SETUP, creation_key=key, creation_hash=digest,
                created_by=actor,
            )
            user = User(
                username=admin["username"], full_name=admin["full_name"], email=admin.get("email", ""),
                mobile=admin.get("mobile", ""), must_change_password=True, created_by=actor,
            )
            user.set_password(admin["password"])
            user.save()
            Membership.objects.create(institution=institution, user=user, role=Role.INSTITUTION_ADMIN, created_by=actor)
            get_or_create_draft(institution, actor)
            audit.log(actor, "institution.created", institution, f"Created {institution.display_name}")
    except IntegrityError:
        # Two identical requests at once: the second finds the first one's institution.
        existing = replayed(key, digest)
        if existing is None:
            raise
        return existing, False
    return institution, True


def update_institution(institution_id, actor, version: int, changes: dict) -> Institution:
    with transaction.atomic():
        institution = Institution.objects.select_for_update().get(pk=institution_id)
        institution.check_version(version)
        if "slug" in changes and changes["slug"] != institution.slug and \
                institution.lifecycle_status != LifecycleStatus.SETUP:
            raise InvalidTransition("The web address can be changed only while the institution is being set up.")
        diff = {
            name: {"from": getattr(institution, name), "to": value}
            for name, value in changes.items()
            if getattr(institution, name) != value
        }
        for name, value in changes.items():
            setattr(institution, name, value)
        institution.save()
        if diff:
            audit.log(actor, "institution.updated", institution, f"Updated {institution.display_name}", changes=diff)
        return institution


def reset_admin_password(institution: Institution, actor, password: str) -> User:
    admin = first_admin(institution)
    if admin is None:
        raise InvalidTransition("This institution has no active Institution Admin.")
    admin.set_password(password)
    admin.must_change_password = True
    admin.save()
    audit.log(actor, "membership.password_reset", admin, f"Reset the password of {admin.full_name}",
              institution=institution)
    return admin
