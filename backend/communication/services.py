"""Conversations, notifications, calls and teacher-led classes (slice 9 S9-01..09, WF-COM §10).

Who may talk about a student is decided afresh on every read and write: a guardian whose active link allows messages,
a teacher who teaches the student now, or staff with communication.manage. Media access only ever comes from a
configured provider (here a test-mode sandbox) as a short-lived signed token bound to the role."""

import datetime as dt
import hashlib
import hmac
import time
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from academics.models import CourseRegistration, EnrollmentPeriod
from academics.teaching import assignments
from accounts.models import Membership, User
from accounts.permissions import active_membership, has_perm, today_for
from common import audit
from common.exceptions import Problem
from communication.models import (
    Call,
    ClassParticipant,
    ClassSession,
    Conversation,
    MediaConfig,
    Message,
    Notification,
    Participant,
    Policy,
    Preference,
)
from students.models import GuardianLink, Student

MANAGE = "communication.manage"
RING_SECONDS = 45
TOKEN_SECONDS = 300


def policy(institution) -> Policy:
    found, _ = Policy.objects.get_or_create(institution=institution)
    return found


def local_now(institution) -> dt.datetime:
    return timezone.localtime(timezone=ZoneInfo(institution.timezone))


def _quiet_window(user, institution) -> tuple:
    pref = Preference.objects.filter(user=user, institution=institution).first()
    if pref and pref.quiet_from and pref.quiet_until:
        return pref.quiet_from, pref.quiet_until
    p = policy(institution)
    return p.quiet_from, p.quiet_until


def quiet_until(user, institution) -> dt.datetime | None:
    """When the user's quiet hours end, if they are in them now; else None."""
    start, end = _quiet_window(user, institution)
    if not start or not end:
        return None
    now = local_now(institution)
    t = now.time().replace(second=0, microsecond=0)
    inside = start <= t < end if start < end else (t >= start or t < end)
    if not inside:
        return None
    finish = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return finish if finish > now else finish + dt.timedelta(days=1)


def notify(user, institution, text: str, link: str = "") -> Notification:
    held = quiet_until(user, institution)
    return Notification.objects.create(
        institution=institution, user=user, text=text[:200], link=link, deliver_after=held or timezone.now()
    )


# Who may talk about a student (S9-02, S9-04)


def _teaches_student(user, institution, student: Student) -> bool:
    mine = assignments(user, institution)
    placed = EnrollmentPeriod.objects.filter(enrollment__student=student, state=EnrollmentPeriod.State.ACTIVE).values(
        "section_id"
    )
    registered = CourseRegistration.objects.filter(
        enrollment__student=student, state=CourseRegistration.State.REGISTERED
    ).values("offering_id")
    return mine.filter(Q(section_id__in=placed) | Q(offering_id__in=registered)).exists()


def role_about(user, institution, student: Student) -> str | None:
    """'guardian', 'teacher' or 'staff' when the user may talk about this student today, else None."""
    membership = active_membership(user, institution)
    if membership is None:
        return None
    if membership.kind == Membership.Kind.GUARDIAN:
        today = today_for(institution)
        links = GuardianLink.objects.filter(
            institution=institution,
            student=student,
            user=user,
            status=GuardianLink.Status.ACTIVE,
            access_messages=True,
            starts_on__lte=today,
        ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        return "guardian" if links.exists() else None
    if membership.kind != Membership.Kind.STAFF:
        return None
    if _teaches_student(user, institution, student):
        return "teacher"
    return "staff" if has_perm(user, institution, MANAGE, student.scope) else None


def _staff(user, institution) -> bool:
    membership = active_membership(user, institution)
    return membership is not None and membership.kind == Membership.Kind.STAFF


def allowed(user, conversation: Conversation) -> Participant | None:
    """The user's participation if they may still take part; a lost relationship marks them left."""
    me = conversation.participants.filter(user=user, left_at__isnull=True).first()
    if me is None:
        return None
    still = (
        role_about(user, conversation.institution, conversation.student) is not None
        if conversation.kind == Conversation.Kind.FAMILY
        else _staff(user, conversation.institution)
    )
    if not still:
        me.left_at = timezone.now()
        me.save(update_fields=["left_at"])
        return None
    return me


def visible(user, institution):
    rows = Conversation.objects.filter(
        institution=institution, participants__user=user, participants__left_at__isnull=True
    )
    return [c for c in rows.select_related("student__person").distinct() if allowed(user, c)]


def start(user, institution, data: dict) -> tuple[Conversation, Message]:
    other = User.objects.filter(pk=data["with"]).first()
    if other is None or other.pk == user.pk:
        raise ValidationError({"with": ["Choose who to write to."]})
    if data.get("student"):
        student = institution.students.filter(pk=data["student"]).first()
        mine = role_about(user, institution, student) if student else None
        theirs = role_about(other, institution, student) if student else None
        if mine is None or theirs is None or (mine == "guardian") == (theirs == "guardian"):
            raise NotFound()  # not this student's family and teacher: nothing to show
        if mine == "guardian" and not policy(institution).guardians_can_start:
            raise PermissionDenied("This school asks teachers to start conversations.")
        kind, roles = Conversation.Kind.FAMILY, {user.pk: mine, other.pk: theirs}
    else:
        student = None
        if not (_staff(user, institution) and _staff(other, institution)):
            raise NotFound()
        kind, roles = Conversation.Kind.STAFF, {user.pk: "staff", other.pk: "staff"}
    with transaction.atomic():
        conversation = Conversation.objects.create(
            institution=institution, kind=kind, student=student, subject=data["subject"], created_by=user
        )
        for person in (user, other):
            Participant.objects.create(conversation=conversation, user=person, role=roles[person.pk])
        message, _ = send(user, conversation, data["body"], data["client_id"])
        return conversation, message


def send(user, conversation: Conversation, body: str, client_id: str) -> tuple[Message, bool]:
    if allowed(user, conversation) is None:
        raise NotFound()
    if found := Message.objects.filter(sender=user, client_message_id=client_id).first():
        if found.conversation_id != conversation.id:
            raise ValidationError({"client_id": ["Use a new id for each message."]})
        return found, False  # a retry: the same message, not a second one
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
        conversation.last_sequence += 1
        conversation.save(update_fields=["last_sequence"])
        message = Message.objects.create(
            conversation=conversation,
            sender=user,
            sequence=conversation.last_sequence,
            client_message_id=client_id,
            body=body,
        )
        mine = conversation.participants.filter(user=user).first()
        if mine and mine.last_read < message.sequence:
            mine.last_read = message.sequence
            mine.save(update_fields=["last_read"])
        about = f" about {conversation.student.person.full_name}" if conversation.student_id else ""
        for other in conversation.participants.filter(left_at__isnull=True).exclude(user=user).select_related("user"):
            notify(
                other.user,
                conversation.institution,
                f"New message{about} from {user.full_name}",
                f"/messages/{conversation.id}",
            )
        return message, True


def mark_read(user, conversation: Conversation, sequence: int) -> None:
    me = allowed(user, conversation)
    if me is None:
        raise NotFound()
    me.last_read = min(max(me.last_read, sequence), conversation.last_sequence)
    me.save(update_fields=["last_read"])


def conversation_item(c: Conversation, viewer, messages: bool = True) -> dict:
    me = c.participants.filter(user=viewer).first()
    people = c.participants.filter(left_at__isnull=True).select_related("user")
    shown = c.messages.filter(sequence__gte=me.sees_from if me else 1).select_related("sender")
    unread = shown.filter(sequence__gt=me.last_read if me else 0).exclude(sender=viewer).count()
    item = {
        "id": str(c.id),
        "kind": c.kind,
        "subject": c.subject,
        "student": {"number": c.student.number, "full_name": c.student.person.full_name} if c.student_id else None,
        "participants": [p.user.full_name for p in people],
        "others": [
            {"id": str(p.user_id), "full_name": p.user.full_name, "role": p.role}
            for p in people
            if p.user_id != viewer.pk
        ],
        "unread": unread,
        "last_sequence": c.last_sequence,
    }
    if messages:
        item["messages"] = [
            {
                "sequence": m.sequence,
                "sender": m.sender.full_name,
                "mine": m.sender_id == viewer.pk,
                "body": m.body,
                "at": m.created_at,
            }
            for m in shown
        ]
    return item


# Calls (S9-06)


def media(institution) -> MediaConfig | None:
    return MediaConfig.objects.filter(institution=institution).first()


def token(config: MediaConfig, kind: str, ref, user, role: str, version: int = 1) -> dict:
    expires = int(time.time()) + TOKEN_SECONDS
    body = f"{kind}:{ref}:{user.pk}:{role}:{version}:{expires}"
    signature = hmac.new(config.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {
        "value": f"{body}.{signature}",
        "role": role,
        "expires_in": TOKEN_SECONDS,
        "provider": config.provider,
        "mode": "test",
    }


def verify(institution, value: str) -> bool:
    """What the media server asks: is this token genuine, unexpired and still current?"""
    config = media(institution)
    try:
        body, signature = value.rsplit(".", 1)
        kind, ref, user, role, version, expires = body.split(":")
    except ValueError:
        return False
    expected = hmac.new(config.secret.encode(), body.encode(), hashlib.sha256).hexdigest() if config else ""
    if not config or not hmac.compare_digest(expected, signature) or int(expires) < time.time():
        return False
    if kind == "class":
        found = ClassParticipant.objects.filter(session_id=ref, user_id=user).first()
        return bool(
            found
            and found.token_version == int(version)
            and found.admission == ClassParticipant.Admission.ADMITTED
            and found.session.state == ClassSession.State.LIVE
        )
    if kind == "call":
        return Call.objects.filter(pk=ref, state=Call.State.CONNECTED).exists()
    return False


def _refresh(call: Call) -> Call:
    if call.state == Call.State.RINGING and call.expires_at < timezone.now():
        call.state, call.ended_at = Call.State.MISSED, timezone.now()
        call.save()
    return call


def ring(user, conversation: Conversation) -> Call:
    if allowed(user, conversation) is None:
        raise NotFound()
    institution = conversation.institution
    if not policy(institution).calls_enabled:
        raise PermissionDenied("Calls are switched off here.")
    others = list(conversation.participants.filter(left_at__isnull=True).exclude(user=user).select_related("user"))
    if len(others) != 1 or allowed(others[0].user, conversation) is None:
        raise Problem(409, "unavailable", "There is nobody to call in this conversation.")
    callee = others[0].user
    if quiet_until(callee, institution):
        raise Problem(409, "unavailable", f"{callee.full_name} is in quiet hours; send a message instead.")
    call = Call.objects.create(
        institution=institution,
        conversation=conversation,
        caller=user,
        callee=callee,
        expires_at=timezone.now() + dt.timedelta(seconds=RING_SECONDS),
    )
    Notification.objects.create(
        institution=institution,
        user=callee,
        text=f"{user.full_name} is calling",
        link=f"/calls/{call.id}",
        deliver_after=timezone.now(),
    )
    return call


def answer(user, call: Call) -> tuple[Call, dict]:
    with transaction.atomic():
        call = _refresh(Call.objects.select_for_update().get(pk=call.pk))
        if call.callee_id != user.pk:
            raise NotFound()
        if call.state != Call.State.RINGING:
            raise Problem(409, "invalid_transition", f"This call is {call.get_state_display().lower()}.")
        if call.conversation and allowed(user, call.conversation) is None:
            raise NotFound()
        config = media(call.institution)
        if config is None:
            call.state, call.reason, call.ended_at = Call.State.FAILED, "integration_not_configured", timezone.now()
            call.save()
            raise Problem(409, "integration_not_configured", "No call provider is set up here.")
        call.state = Call.State.CONNECTED
        call.save()
        return call, token(config, "call", call.id, user, "participant")


def finish(user, call: Call, how: str) -> Call:
    with transaction.atomic():
        call = _refresh(Call.objects.select_for_update().get(pk=call.pk))
        if user.pk not in (call.caller_id, call.callee_id):
            raise NotFound()
        if call.state in Call.FINAL:
            return call
        if how == "decline" and (call.callee_id != user.pk or call.state != Call.State.RINGING):
            raise Problem(409, "invalid_transition", "Only a ringing call is declined, by who it rings.")
        call.state = {"decline": Call.State.DECLINED, "cancel": Call.State.CANCELED}.get(
            how, Call.State.CANCELED if call.state == Call.State.RINGING else Call.State.ENDED
        )
        call.ended_at = timezone.now()
        call.save()
        return call


def call_item(call: Call, viewer) -> dict:
    call = _refresh(call)
    item = {
        "id": str(call.id),
        "state": call.state,
        "state_label": call.get_state_display(),
        "reason": call.reason,
        "caller": call.caller.full_name,
        "callee": call.callee.full_name,
        "token": None,
    }
    config = media(call.institution)
    if call.state == Call.State.CONNECTED and config and viewer.pk in (call.caller_id, call.callee_id):
        item["token"] = token(config, "call", call.id, viewer, "participant")
    return item


# Teacher-led classes (S9-07..09)


def _roster_users(session: ClassSession) -> set:
    if session.section_id:
        rows = EnrollmentPeriod.objects.filter(section=session.section, state=EnrollmentPeriod.State.ACTIVE)
    else:
        rows = CourseRegistration.objects.filter(offering=session.offering, state=CourseRegistration.State.REGISTERED)
    return set(rows.values_list("enrollment__student__user_id", flat=True))


def schedule(user, institution, target, title: str, starts_at) -> ClassSession:
    kind = "section" if target.__class__.__name__ == "Section" else "offering"
    if not assignments(user, institution).filter(**{kind: target}).exists():
        raise NotFound()  # only the class's own teacher hosts it; students can't start one
    if not policy(institution).classes_enabled:
        raise PermissionDenied("Online classes are switched off here.")
    return ClassSession.objects.create(
        institution=institution, host=user, title=title, starts_at=starts_at, **{kind: target}
    )


def refresh(session: ClassSession) -> ClassSession:
    """A paused class ends once the grace has run out without its teacher (S9-07)."""
    if session.state == ClassSession.State.PAUSED and timezone.now() - session.paused_at >= dt.timedelta(
        seconds=session.GRACE_SECONDS
    ):
        session.state, session.ended_at = (
            ClassSession.State.ENDED,
            session.paused_at + dt.timedelta(seconds=session.GRACE_SECONDS),
        )
        session.save()
        for p in session.participants.filter(joined_at__isnull=False):
            _leave(p, session.ended_at)
    return session


def _leave(p: ClassParticipant, at=None) -> None:
    if p.joined_at:
        p.seconds += max(int(((at or timezone.now()) - p.joined_at).total_seconds()), 0)
        p.joined_at = None
        p.save(update_fields=["seconds", "joined_at"])


def join(user, session: ClassSession) -> tuple[int, dict]:
    with transaction.atomic():
        session = refresh(ClassSession.objects.select_for_update().get(pk=session.pk))
        if session.state == ClassSession.State.ENDED:
            raise Problem(409, "ended", "This class has ended.")
        config = media(session.institution)
        if session.host_id == user.pk:
            if config is None:
                raise Problem(409, "integration_not_configured", "No class provider is set up here.")
            p, _ = ClassParticipant.objects.get_or_create(
                session=session, user=user, defaults={"role": "host", "admission": "admitted"}
            )
            p.joined_at = p.joined_at or timezone.now()
            p.save()
            session.state, session.paused_at = ClassSession.State.LIVE, None
            session.save()
            return 200, {
                "admission": "admitted",
                "token": token(config, "class", session.id, user, "host", p.token_version),
            }
        if user.pk not in _roster_users(session):
            raise NotFound()
        if session.state == ClassSession.State.SCHEDULED:
            raise Problem(409, "not_started", "The teacher hasn't started the class yet.")
        if session.state == ClassSession.State.PAUSED:
            raise Problem(409, "paused", "The class is paused until the teacher is back.")
        p, _ = ClassParticipant.objects.get_or_create(session=session, user=user, defaults={"role": "attendee"})
        if p.admission == ClassParticipant.Admission.REMOVED:
            raise PermissionDenied("The teacher removed you from this class.")
        if p.admission == ClassParticipant.Admission.WAITING:
            return 202, {"admission": "waiting", "participant": str(p.id), "token": None}
        if config is None:
            raise Problem(409, "integration_not_configured", "No class provider is set up here.")
        if p.joined_at is None:  # a reconnect while present doesn't start a second stay
            p.joined_at = timezone.now()
            p.save(update_fields=["joined_at"])
        return 200, {
            "admission": "admitted",
            "participant": str(p.id),
            "token": token(config, "class", session.id, user, "attendee", p.token_version),
        }


def leave(user, session: ClassSession) -> ClassSession:
    with transaction.atomic():
        session = ClassSession.objects.select_for_update().get(pk=session.pk)
        p = session.participants.filter(user=user).first()
        if p is None:
            raise NotFound()
        _leave(p)
        hosts_present = session.participants.filter(role="host", joined_at__isnull=False).exists()
        if session.state == ClassSession.State.LIVE and not hosts_present:
            session.state, session.paused_at = ClassSession.State.PAUSED, timezone.now()  # students pause at once
            session.save()
        return session


def host_action(user, session: ClassSession, participant: ClassParticipant | None, action: str) -> ClassSession:
    if session.host_id != user.pk:
        raise NotFound()
    with transaction.atomic():
        if action == "end":
            session.state, session.ended_at = ClassSession.State.ENDED, timezone.now()
            session.save()
            for p in session.participants.filter(joined_at__isnull=False):
                _leave(p)
            audit.log(user, "class.ended", session, f"{session.title} ended", institution=session.institution)
            return session
        if action == "admit":
            participant.admission = ClassParticipant.Admission.ADMITTED
        else:
            participant.admission = ClassParticipant.Admission.REMOVED
            participant.token_version += 1  # tokens already handed out stop working
            _leave(participant)
        participant.save()
        return session


def session_item(session: ClassSession, viewer) -> dict:
    session = refresh(session)
    target = session.section or session.offering
    from attendance.services import label

    item = {
        "id": str(session.id),
        "title": session.title,
        "state": session.state,
        "state_label": session.get_state_display(),
        "starts_at": session.starts_at,
        "host": session.host.full_name,
        "target": {
            "kind": "section" if session.section_id else "offering",
            "id": str(target.id),
            "label": label(target),
        },
        "recording": False,  # off until an approved recording policy exists (D-13)
        "is_host": session.host_id == viewer.pk,
    }
    if session.host_id == viewer.pk:
        item["participants"] = [
            {
                "id": str(p.id),
                "full_name": p.user.full_name,
                "role": p.role,
                "admission": p.admission,
                "present": p.joined_at is not None,
                "seconds": p.seconds,
            }
            for p in session.participants.select_related("user").order_by("role", "user__full_name")
        ]
    return item


def classes_for(user, institution):
    """Classes a user hosts or is on the roster of."""
    rows = ClassSession.objects.filter(institution=institution).select_related("section", "offering__course", "host")
    return [s for s in rows if s.host_id == user.pk or user.pk in _roster_users(s)]
