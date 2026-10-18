"""Campuses and departments, under institution/ on an institution's own host."""

from django.urls import path

from organization.views import CampusDetail, CampusList, DepartmentDetail, DepartmentList

urlpatterns = [
    path("campuses", CampusList.as_view()),
    path("campuses/<uuid:pk>", CampusDetail.as_view()),
    path("departments", DepartmentList.as_view()),
    path("departments/<uuid:pk>", DepartmentDetail.as_view()),
]
