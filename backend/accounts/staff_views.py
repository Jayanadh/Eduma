"""Staff on an institution's own host: list, add, detail and details (slice 2 spec §5)."""

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.models import Membership
from accounts.permissions import can_manage_person
from accounts.role_views import holds_any
from accounts.staff import create_staff, own_membership, visible_memberships
from accounts.staff_serializers import DetailsInput, StaffInput, staff_detail, staff_item
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

    def managed(self) -> Membership:
        """The membership in the URL, for a change the caller must be allowed to make to that person."""
        found = Membership.objects.filter(institution=self.request.institution, pk=self.kwargs["pk"]).first()
        if found is not None and found.user_id == self.request.user.id:
            raise own_membership()
        found = self.person()
        if not can_manage_person(self.request.user, found):
            raise PermissionDenied("You can't change this person: they hold roles beyond yours.")
        return found


class StaffList(StaffView):
    pagination_class = Pages

    def get(self, request):
        queryset = visible_memberships(request.user, request.institution).select_related("user", "institution")
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
        data = DetailsInput(data=request.data)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        with transaction.atomic():
            membership = Membership.objects.select_for_update().get(pk=self.managed().pk)
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
