"""Roles and staff, under institution/ on an institution's own host."""

from django.urls import path

from accounts.approvals import Approvals
from accounts.role_views import PermissionsView, RoleDetail, RoleList
from accounts.staff_views import (
    ApproveRole,
    EndRole,
    GiveRole,
    RejectRole,
    Remove,
    ResetPassword,
    Restore,
    StaffDetail,
    StaffList,
)

urlpatterns = [
    path("permissions", PermissionsView.as_view()),
    path("roles", RoleList.as_view()),
    path("roles/<uuid:pk>", RoleDetail.as_view()),
    path("staff", StaffList.as_view()),
    path("staff/<uuid:pk>", StaffDetail.as_view()),
    path("staff/<uuid:pk>/assignments", GiveRole.as_view()),
    path("staff/<uuid:pk>/assignments/<uuid:aid>/end", EndRole.as_view()),
    path("staff/<uuid:pk>/assignments/<uuid:aid>/approve", ApproveRole.as_view()),
    path("staff/<uuid:pk>/assignments/<uuid:aid>/reject", RejectRole.as_view()),
    path("approvals", Approvals.as_view()),
    path("staff/<uuid:pk>/password", ResetPassword.as_view()),
    path("staff/<uuid:pk>/remove", Remove.as_view()),
    path("staff/<uuid:pk>/restore", Restore.as_view()),
]
