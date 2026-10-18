"""Staff on an institution's own host: list, add, detail and details (slice 2 spec §5)."""

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.models import Membership, RoleAssignment
from accounts.permissions import can_manage_person, today_for
from accounts.role_views import holds_any
from accounts.staff import (
    approve_request,
    create_staff,
    end_assignment,
    give_role,
    own_membership,
    reject_request,
    remove,
    reset_password,
    restore,
    visible_memberships,
)
from accounts.staff_serializers import (
    AssignmentInput,
    DetailsInput,
    StaffInput,
    current_roles,
    staff_detail,
    staff_item,
)
from common import audit
from common.pagination import Pages


class StaffView(GenericAPIView):
    def get_permissions(self):
        return [holds_any("membership.read" if self.request.method == "GET" else "membership.assign")()]

    def person(self) -> Membership:
        """The membership in the URL, if the caller may see it; otherwise it does not exist for them."""
        membership = visible_memberships(self.request.user, self.request.institution).filter(pk=self.kwargs["pk"])
        found = membership.select_related("user", "institution").first()
        if found is None:
            raise NotFound()
        return found

    def target(self) -> Membership:
        """The membership in the URL, refusing the caller's own."""
        found = Membership.objects.filter(institution=self.request.institution, pk=self.kwargs["pk"]).first()
        if found is not None and found.user_id == self.request.user.id:
            raise own_membership()
        return self.person()

    def managed(self) -> Membership:
        """The membership in the URL, for a change the caller must be allowed to make to that person."""
        found = self.target()
        if not can_manage_person(self.request.user, found):
            raise PermissionDenied("You can't change this person: they hold roles beyond yours.")
        return found


class StaffList(StaffView):
    pagination_class = Pages

    def get(self, request):
        queryset = visible_memberships(request.user, request.institution).select_related("user", "institution")
        queryset = queryset.prefetch_related(current_roles(today_for(request.institution)))
        if len(search := request.query_params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(Q(user__full_name__icontains=search) | Q(user__username__icontains=search))
        page = self.paginate_queryset(queryset.order_by("user__full_name"))
        return self.get_paginated_response([staff_item(membership) for membership in page])

    def post(self, request):
        data = StaffInput(data=request.data)
        data.is_valid(raise_exception=True)
        membership = create_staff(request.user, request.institution, data.validated_data)
        return Response(staff_detail(membership, request.user), status=status.HTTP_201_CREATED)


class StaffDetail(StaffView):
    def get(self, request, pk):
        return Response(staff_detail(self.person(), request.user))

    def patch(self, request, pk):
        found = self.managed()  # the record first: someone who may not see it learns nothing from the body's errors
        data = DetailsInput(data=request.data)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        with transaction.atomic():
            membership = Membership.objects.select_for_update().get(pk=found.pk)
            membership.check_version(changes.pop("version"))
            user = membership.user
            diff = {
                name: {"from": getattr(user, name), "to": value}
                for name, value in changes.items()
                if getattr(user, name) != value
            }
            for name, value in changes.items():
                setattr(user, name, value)
            user.save()
            membership.save()  # the details' version lives on the membership
            if diff:
                summary = f"Changed {user.full_name}'s details"
                audit.log(request.user, "staff.updated", membership, summary, changes=diff)
        return Response(staff_detail(membership, request.user))


class ReasonInput(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class RemoveInput(ReasonInput):
    version = serializers.IntegerField()


class PasswordInput(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False)


class ActionView(StaffView):
    """Changes to one person: always POST, and never to the caller's own membership."""

    def get_permissions(self):
        return [holds_any("membership.assign")()]

    def done(self, membership: Membership, code: int = status.HTTP_200_OK) -> Response:
        membership.refresh_from_db()
        return Response(staff_detail(membership, self.request.user), status=code)


class GiveRole(ActionView):
    def post(self, request, pk):
        membership = self.target()
        data = AssignmentInput(data=request.data)
        data.is_valid(raise_exception=True)
        give_role(request.user, membership, data.validated_data)
        return self.done(membership, status.HTTP_201_CREATED)


class EndRole(ActionView):
    def post(self, request, pk, aid):
        membership = self.target()
        data = ReasonInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = membership.assignments.filter(pk=aid).select_related("institution", "membership__user").first()
        if row is None:
            raise NotFound()
        end_assignment(request.user, row, data.validated_data["reason"])
        return self.done(membership)


class ResetPassword(ActionView):
    def post(self, request, pk):
        membership = self.managed()
        data = PasswordInput(data=request.data)
        data.is_valid(raise_exception=True)
        reset_password(request.user, membership, data.validated_data["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class Remove(ActionView):
    def post(self, request, pk):
        found = self.managed()
        data = RemoveInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        membership = remove(request.user, found, values["reason"], values["version"])
        return self.done(membership)


class VersionInput(serializers.Serializer):
    version = serializers.IntegerField()


class Restore(ActionView):
    def post(self, request, pk):
        found = self.target()
        data = VersionInput(data=request.data)
        data.is_valid(raise_exception=True)
        membership = restore(request.user, found, data.validated_data["version"])
        return self.done(membership)


class Decide(ActionView):
    """Approve or turn down a role that waits for approval."""

    def row(self, aid) -> RoleAssignment:
        # target(): a request for the caller's own roles is someone else's to decide.
        found = self.target().assignments.filter(pk=aid).select_related("institution", "membership__user").first()
        if found is None:
            raise NotFound()
        return found


class ApproveRole(Decide):
    def post(self, request, pk, aid):
        approve_request(request.user, self.row(aid))
        return self.done(self.person())


class RejectRole(Decide):
    def post(self, request, pk, aid):
        row = self.row(aid)
        reason = self.data_reason()
        reject_request(request.user, row, reason)
        return self.done(self.person())

    def data_reason(self) -> str:
        data = ReasonInput(data=self.request.data)
        data.is_valid(raise_exception=True)
        return data.validated_data["reason"]
