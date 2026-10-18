"""Final review of slice 3: the two-person approval must not be self-approved, stuck, or bypassed by editing a role."""

import datetime as dt

from accounts.models import Membership, RoleAssignment
from accounts.permissions import has_perm, today_for
from configuration import services
from configuration.models import SettingRevision
from configuration.registry import setting
from testing import factories

STAFF = "/api/v1/institution/staff"


def approval_on(institution):
    SettingRevision.objects.create(
        institution=institution,
        key="access.role_approval",
        number=1,
        value=True,
        status="published",
        effective_from=today_for(institution),
    )


def mid(user, institution) -> str:
    return str(Membership.objects.get(user=user, institution=institution).id)


def test_nobody_approves_a_role_requested_for_themselves(world, client_for):
    """Review #1."""
    approval_on(world.a)
    leaving = factories.member(world.a, role="institution_admin", ends_on=today_for(world.a) + dt.timedelta(days=30))
    admin = client_for(world.a.slug, world.a_admin)
    body = {"role": "institution_admin", "scope_type": "institution"}
    admin.post(f"{STAFF}/{mid(leaving, world.a)}/assignments", body, format="json")
    row = RoleAssignment.objects.get(membership__user=leaving, status="pending")
    own = client_for(world.a.slug, leaving)
    response = own.post(f"{STAFF}/{mid(leaving, world.a)}/assignments/{row.id}/approve")
    assert response.status_code == 403 and response.json()["code"] == "own_membership"
    assert own.get("/api/v1/institution/approvals").json()["roles"] == []
    row.refresh_from_db()
    assert row.status == "pending"


def test_turning_approval_off_never_gets_stuck(world, client_for):
    """Review #2: with nobody else left to approve, a publisher may still turn approval off; it is audited."""
    from common.models import AuditEvent

    second = factories.member(world.a, role="institution_admin")
    approval_on(world.a)
    RoleAssignment.objects.filter(membership__user=second).update(status="ended")
    draft = services.open_draft(world.a, world.a_admin, "access.role_approval")
    draft = services.save_draft(world.a, world.a_admin, "access.role_approval", draft.version, False)
    done = services.submit(world.a, world.a_admin, "access.role_approval", draft.version, today_for(world.a), "Alone")
    assert done.status == "published"
    assert setting(world.a, "access.role_approval") is False
    event = AuditEvent.objects.get(action="setting.published", object_id=str(done.id))
    assert "nobody else could approve" in event.summary


def test_turning_approval_on_needs_two_people_who_could_approve_any_role(world):
    """Review #2 (related): a custom-role assigner cannot approve an Institution Admin request."""
    import pytest
    from rest_framework.exceptions import ValidationError

    helper = factories.custom_role(world.a, permissions=["membership.assign", "membership.read"])
    factories.member(world.a, custom_role=helper)
    draft = services.open_draft(world.a, world.a_admin, "access.role_approval")
    with pytest.raises(ValidationError):
        services.save_draft(world.a, world.a_admin, "access.role_approval", draft.version, True)


def test_held_roles_cannot_gain_powers_while_approval_is_on(world, client_for):
    """Review #3."""
    factories.member(world.a, role="institution_admin")
    approval_on(world.a)
    viewer = factories.custom_role(world.a, permissions=["membership.read"], name="Viewer")
    holder = factories.member(world.a, custom_role=viewer)
    admin = client_for(world.a.slug, world.a_admin)
    body = {"version": viewer.version, "permissions": ["membership.assign", "membership.read"]}
    response = admin.patch(f"/api/v1/institution/roles/{viewer.id}", body, format="json")
    assert response.status_code == 409 and response.json()["code"] == "needs_approval"
    assert not has_perm(holder, world.a, "membership.assign")
    unheld = factories.custom_role(world.a, permissions=["membership.read"], name="Spare")
    body = {"version": unheld.version, "permissions": ["membership.assign", "membership.read"]}
    assert admin.patch(f"/api/v1/institution/roles/{unheld.id}", body, format="json").status_code == 200
