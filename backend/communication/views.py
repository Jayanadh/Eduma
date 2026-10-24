"""Messages, notifications, calls and classes, under communication/ on an institution's own host (slice 9)."""

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import CourseOffering, Section
from academics.views import valid
from accounts.models import Membership
from accounts.permissions import active_membership, has_perm
from communication import services
from communication.models import Call, ClassSession, Conversation, MediaConfig, Notification, Preference
from configuration.gates import require_module


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class CommsView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.membership = (
            active_membership(request.user, request.institution) if request.site_kind == "institution" else None
        )
        if self.membership is None or self.membership.kind == Membership.Kind.APPLICANT:
            raise NotFound()
        require_module(request.institution, "communication")

    def conversation(self, pk) -> Conversation:
        found = _found(
            Conversation.objects.filter(institution=self.request.institution).select_related("student__person"), pk
        )
        if services.allowed(self.request.user, found) is None:
            raise NotFound()
        return found

    def manager(self):
        if not has_perm(self.request.user, self.request.institution, services.MANAGE):
            raise PermissionDenied("Only someone who manages communication can change this.")


class StartInput(serializers.Serializer):
    student = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=150)
    body = serializers.CharField(max_length=4000)
    client_id = serializers.CharField(max_length=64)


class Conversations(CommsView):
    def get(self, request):
        return Response(
            [
                services.conversation_item(c, request.user, messages=False)
                for c in services.visible(request.user, request.institution)
            ]
        )

    def post(self, request):
        data = valid(StartInput, request.data)
        data["with"] = serializers.UUIDField().to_internal_value(request.data.get("with"))  # "with" is a Python keyword
        conversation, _ = services.start(request.user, request.institution, data)
        return Response(services.conversation_item(conversation, request.user), status=status.HTTP_201_CREATED)


class ConversationDetail(CommsView):
    def get(self, request, pk):
        return Response(services.conversation_item(self.conversation(pk), request.user))


class Messages(CommsView):
    def post(self, request, pk):
        conversation = _found(Conversation.objects.filter(institution=request.institution), pk)
        body, client_id = str(request.data.get("body", "")).strip(), str(request.data.get("client_id", "")).strip()
        if not body or not client_id:
            raise serializers.ValidationError({"body": ["Write the message."]})
        message, made = services.send(request.user, conversation, body, client_id)
        return Response(
            {"sequence": message.sequence, "body": message.body},
            status=status.HTTP_201_CREATED if made else status.HTTP_200_OK,
        )


class Read(CommsView):
    def post(self, request, pk):
        services.mark_read(request.user, self.conversation(pk), int(request.data.get("sequence", 0)))
        return Response(status=status.HTTP_204_NO_CONTENT)


class Notifications(CommsView):
    def get(self, request):
        from django.utils import timezone

        rows = Notification.objects.filter(
            user=request.user, institution=request.institution, deliver_after__lte=timezone.now()
        )
        return Response(
            [
                {"id": str(n.id), "text": n.text, "link": n.link, "at": n.created_at, "read": n.read_at is not None}
                for n in rows[:50]
            ]
        )


class Contacts(CommsView):
    """Who this user may start a conversation with about a student (or, for staff, other staff)."""

    def get(self, request):
        student = request.query_params.get("student")
        if student:
            found = _found(request.institution.students.select_related("person"), student)
            mine = services.role_about(request.user, request.institution, found)
            if mine is None:
                raise NotFound()
            from students.models import GuardianLink

            people = []
            if mine == "guardian":
                staff = Membership.objects.filter(
                    institution=request.institution, kind=Membership.Kind.STAFF
                ).select_related("user")
                people = [m.user for m in staff if services.role_about(m.user, request.institution, found) == "teacher"]
            else:
                links = GuardianLink.objects.filter(
                    student=found, status="active", access_messages=True
                ).select_related("user")
                people = [link.user for link in links if link.user_id]
            return Response([{"id": str(u.id), "full_name": u.full_name} for u in people])
        if self.membership.kind != Membership.Kind.STAFF:
            return Response([])
        staff = Membership.objects.filter(
            institution=request.institution, kind=Membership.Kind.STAFF, status="active"
        ).exclude(user=request.user)
        return Response([{"id": str(m.user_id), "full_name": m.user.full_name} for m in staff.select_related("user")])


class PolicyView(CommsView):
    def get(self, request):
        p = services.policy(request.institution)
        return Response(
            {
                "guardians_can_start": p.guardians_can_start,
                "calls_enabled": p.calls_enabled,
                "classes_enabled": p.classes_enabled,
                "media": bool(services.media(request.institution)),
            }
        )

    def put(self, request):
        self.manager()
        p = services.policy(request.institution)
        for name in ("guardians_can_start", "calls_enabled", "classes_enabled"):
            if name in request.data:
                setattr(p, name, bool(request.data[name]))
        p.save()
        return self.get(request)


class MediaView(CommsView):
    def put(self, request):
        self.manager()
        if request.data.get("provider") != "sandbox" or not str(request.data.get("secret", "")).strip():
            raise serializers.ValidationError(
                {"provider": ["Only the test-mode sandbox exists until a provider is chosen."]}
            )
        MediaConfig.objects.update_or_create(
            institution=request.institution, defaults={"provider": "sandbox", "secret": request.data["secret"]}
        )
        return Response({"provider": "sandbox", "mode": "test"})


class Verify(CommsView):
    def post(self, request):
        return Response({"valid": services.verify(request.institution, str(request.data.get("token", "")))})


class Preferences(CommsView):
    def put(self, request):
        fields = serializers.TimeField(allow_null=True, required=False)
        data = {
            k: fields.to_internal_value(request.data[k]) if request.data.get(k) else None
            for k in ("quiet_from", "quiet_until")
        }
        Preference.objects.update_or_create(user=request.user, institution=request.institution, defaults=data)
        return Response({k: v.strftime("%H:%M") if v else None for k, v in data.items()})


class Calls(CommsView):
    def post(self, request):
        conversation = _found(
            Conversation.objects.filter(institution=request.institution), request.data.get("conversation")
        )
        return Response(
            services.call_item(services.ring(request.user, conversation), request.user), status=status.HTTP_201_CREATED
        )


class CallDetail(CommsView):
    def call(self, pk) -> Call:
        found = _found(Call.objects.filter(institution=self.request.institution).select_related("caller", "callee"), pk)
        if self.request.user.pk not in (found.caller_id, found.callee_id):
            raise NotFound()
        return found

    def get(self, request, pk):
        return Response(services.call_item(self.call(pk), request.user))


class CallAction(CallDetail):
    action = "accept"

    def post(self, request, pk):
        call = self.call(pk)
        if self.action == "accept":
            call, token = services.answer(request.user, call)
            return Response({**services.call_item(call, request.user), "token": token})
        return Response(services.call_item(services.finish(request.user, call, self.action), request.user))


class ClassInput(serializers.Serializer):
    section = serializers.UUIDField(required=False, allow_null=True)
    offering = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=150)
    starts_at = serializers.DateTimeField()


class Classes(CommsView):
    def get(self, request):
        return Response(
            [services.session_item(s, request.user) for s in services.classes_for(request.user, request.institution)]
        )

    def post(self, request):
        data = valid(ClassInput, request.data)
        if data.get("section"):
            target = _found(Section.objects.filter(institution=request.institution), data["section"])
        else:
            target = _found(
                CourseOffering.objects.filter(institution=request.institution).select_related("course"),
                data.get("offering"),
            )
        made = services.schedule(request.user, request.institution, target, data["title"], data["starts_at"])
        return Response(services.session_item(made, request.user), status=status.HTTP_201_CREATED)


class ClassView(CommsView):
    def session(self, pk) -> ClassSession:
        found = _found(
            ClassSession.objects.filter(institution=self.request.institution).select_related(
                "host", "section", "offering__course"
            ),
            pk,
        )
        if found.host_id != self.request.user.pk and self.request.user.pk not in services._roster_users(found):
            raise NotFound()
        return found


class ClassDetail(ClassView):
    def get(self, request, pk):
        return Response(services.session_item(self.session(pk), request.user))


class Join(ClassView):
    def post(self, request, pk):
        session = self.session(pk)
        code, body = services.join(request.user, session)
        session.refresh_from_db()
        return Response({**body, "session": services.session_item(session, request.user)}, status=code)


class Leave(ClassView):
    def post(self, request, pk):
        return Response(services.session_item(services.leave(request.user, self.session(pk)), request.user))


class HostAction(ClassView):
    action = "admit"

    def post(self, request, pk, participant=None):
        session = self.session(pk)
        found = _found(session.participants.all(), participant) if participant else None
        return Response(
            services.session_item(services.host_action(request.user, session, found, self.action), request.user)
        )
