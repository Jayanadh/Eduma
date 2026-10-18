import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import today_for
from common.exceptions import Problem
from configuration import services
from configuration.models import SettingRevision
from configuration.registry import setting
from testing import factories

YEAR = "academic.year_start"
APPROVAL = "access.role_approval"


def change(institution, actor, key, value, starts=None, reason="Board calendar"):
    draft = services.open_draft(institution, actor, key)
    draft = services.save_draft(institution, actor, key, draft.version, value)
    return services.submit(institution, actor, key, draft.version, starts or today_for(institution), reason)


def code_of(error: Problem) -> str:
    return error.problem_code


def test_future_change_leaves_today_alone(world, monkeypatch):
    today = today_for(world.a)
    first = change(world.a, world.a_admin, YEAR, 4, today + dt.timedelta(days=30))
    assert first.status == "published"
    assert setting(world.a, YEAR) == 6
    assert setting(world.a, YEAR, on=today + dt.timedelta(days=30)) == 4
    later = timezone.now() + dt.timedelta(days=31)
    monkeypatch.setattr(timezone, "now", lambda: later)
    assert setting(world.a, YEAR) == 4
    first.refresh_from_db()
    assert (first.status, first.value) == ("published", 4)


def test_later_publish_cancels_unstarted_schedule(world):
    today = today_for(world.a)
    past = SettingRevision.objects.create(
        institution=world.a,
        key=YEAR,
        number=1,
        value=8,
        status="published",
        effective_from=today - dt.timedelta(days=5),
    )
    scheduled = change(world.a, world.a_admin, YEAR, 4, today + dt.timedelta(days=30))
    sooner = change(world.a, world.a_admin, YEAR, 1, today + dt.timedelta(days=10))
    scheduled.refresh_from_db()
    past.refresh_from_db()
    assert scheduled.status == "superseded"
    assert sooner.status == "published" and past.status == "published"
    assert setting(world.a, YEAR) == 8


def test_maker_is_not_checker(world):
    deputy = factories.member(world.a, role="institution_admin")
    pending = change(world.a, world.a_admin, APPROVAL, True)
    assert pending.status == "pending"
    with pytest.raises(Problem) as own:
        services.approve(world.a, world.a_admin, pending.id, pending.version)
    assert code_of(own.value) == "own_request"
    returned = services.return_to_draft(world.a, deputy, pending.id, pending.version, "Not until term ends")
    assert (returned.status, returned.return_note) == ("draft", "Not until term ends")
    again = services.submit(world.a, world.a_admin, APPROVAL, returned.version, today_for(world.a), "Term ended")
    approved = services.approve(world.a, deputy, again.id, again.version)
    assert (approved.status, approved.approved_by) == ("published", deputy)
    assert setting(world.a, APPROVAL) is True


def test_single_publisher_cannot_turn_approval_on_but_can_turn_it_off(world):
    with pytest.raises(ValidationError):  # value check comes first: one approver cannot turn approval on
        change(world.a, world.a_admin, APPROVAL, True)
    # Off is the way out, so it never waits for a second person who does not exist (final review #2).
    assert change(world.a, world.a_admin, APPROVAL, False).status == "published"


def test_editor_without_publish_cannot_publish(world):
    editor = factories.member(world.a, custom_role=factories.custom_role(world.a, permissions=["configuration.edit"]))
    with pytest.raises(PermissionDenied):
        change(world.a, editor, YEAR, 4)


def test_effective_from_in_the_past_is_refused(world):
    draft = services.open_draft(world.a, world.a_admin, YEAR)
    with pytest.raises(ValidationError) as refused:
        services.submit(world.a, world.a_admin, YEAR, draft.version, today_for(world.a) - dt.timedelta(days=1), "x")
    assert "effective_from" in refused.value.detail


def test_approval_rechecks_the_value(world):
    from accounts.models import RoleAssignment

    deputy = factories.member(world.a, role="institution_admin")
    pending = change(world.a, world.a_admin, APPROVAL, True)
    # Before the decision, the sender and the deputy stop being admins: one assigner is left, too few for approvals.
    RoleAssignment.objects.filter(membership__user__in=[world.a_admin, deputy]).update(status="ended")
    last = factories.member(world.a, role="institution_admin")
    with pytest.raises(ValidationError):
        services.approve(world.a, last, pending.id, pending.version)
    pending.refresh_from_db()
    assert pending.status == "pending"


def test_restore_puts_old_value_in_a_draft(world):
    first = change(world.a, world.a_admin, YEAR, 4)
    change(world.a, world.a_admin, YEAR, 9)
    restored = services.restore(world.a, world.a_admin, YEAR, first.id, None)
    assert (restored.status, restored.value) == ("draft", 4)
    with pytest.raises(Problem) as stale:
        services.restore(world.a, world.a_admin, YEAR, first.id, restored.version - 1)
    assert code_of(stale.value) == "version_conflict"


def test_withdraw_and_one_open_revision(world):
    one = services.open_draft(world.a, world.a_admin, YEAR)
    assert services.open_draft(world.a, world.a_admin, YEAR).id == one.id
    gone = services.withdraw(world.a, world.a_admin, YEAR, one.version)
    assert gone.status == "withdrawn"
    factories.member(world.a, role="institution_admin")
    change(world.a, world.a_admin, APPROVAL, True)
    with pytest.raises(Problem) as waiting:
        services.open_draft(world.a, world.a_admin, APPROVAL)
    assert code_of(waiting.value) == "change_waiting"


def test_save_checks_the_value(world):
    draft = services.open_draft(world.a, world.a_admin, YEAR)
    with pytest.raises(ValidationError) as bad:
        services.save_draft(world.a, world.a_admin, YEAR, draft.version, 13)
    assert "value" in bad.value.detail
