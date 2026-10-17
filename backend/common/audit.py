"""One call records an audit event: audit.log(actor, "institution.updated", institution, "Updated Aster School",
changes={"contact_phone": {"from": "…", "to": "…"}})."""

from django.db import models

from common.models import AuditEvent


def log(actor, action: str, target: models.Model, summary: str, *, institution=None, changes: dict | None = None):
    from institutions.models import Institution

    if institution is None:
        institution = target if isinstance(target, Institution) else None
    institution_id = institution.pk if institution is not None else getattr(target, "institution_id", None)
    return AuditEvent.objects.create(
        actor=actor if actor is not None and actor.is_authenticated else None,
        institution_id=institution_id,
        action=action,
        object_type=target._meta.model_name,
        object_id=str(target.pk),
        summary=summary[:255],
        changes=changes or {},
    )
