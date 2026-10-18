"""Roles and staff, under institution/ on an institution's own host."""

from django.urls import path

from accounts.role_views import PermissionsView, RoleDetail, RoleList

urlpatterns = [
    path("permissions", PermissionsView.as_view()),
    path("roles", RoleList.as_view()),
    path("roles/<uuid:pk>", RoleDetail.as_view()),
]
