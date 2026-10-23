"""Staged imports, under institution/imports on an institution's own host."""

from django.urls import path

from imports import views

urlpatterns = [
    path("", views.JobList.as_view()),
    path("/<uuid:pk>", views.JobDetail.as_view()),
    path("/<uuid:pk>/rows", views.JobRows.as_view()),
    path("/<uuid:pk>/rows/<uuid:row>/decide", views.Decide.as_view()),
]
