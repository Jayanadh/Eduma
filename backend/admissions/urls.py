"""Admissions for staff, under institution/admissions/ on an institution's own host."""

from django.urls import path

from admissions import cycle_views

urlpatterns = [
    path("cycles", cycle_views.CycleList.as_view()),
    path("cycles/<uuid:pk>", cycle_views.CycleDetail.as_view()),
    path("cycles/<uuid:pk>/publish", cycle_views.Publish.as_view()),
    path("cycles/<uuid:pk>/close", cycle_views.Close.as_view()),
]
