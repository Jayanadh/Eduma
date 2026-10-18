"""Roles and staff, under institution/ on an institution's own host."""

from django.urls import path

from accounts.role_views import PermissionsView, RoleDetail, RoleList
from accounts.staff_views import StaffDetail, StaffList

urlpatterns = [
    path("permissions", PermissionsView.as_view()),
    path("roles", RoleList.as_view()),
    path("roles/<uuid:pk>", RoleDetail.as_view()),
    path("staff", StaffList.as_view()),
    path("staff/<uuid:pk>", StaffDetail.as_view()),
]
