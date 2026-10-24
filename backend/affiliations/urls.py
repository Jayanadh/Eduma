"""Affiliation, under institution/affiliations on an institution's own host."""

from django.urls import path

from affiliations import views

urlpatterns = [
    path("", views.Grants.as_view()),
    path("/<uuid:pk>/approve", views.Approve.as_view()),
    path("/<uuid:pk>/revoke", views.Revoke.as_view()),
    path("/<uuid:pk>/batches", views.Batches.as_view()),
    path("/batches/<uuid:pk>", views.BatchDetail.as_view()),
    path("/batches/<uuid:pk>/rows/<uuid:row>", views.BatchRow.as_view()),
    path("/batches/<uuid:pk>/submit", views.Submit.as_view()),
    path("/batches/<uuid:pk>/revise", views.Revise.as_view()),
    path("/received", views.Received.as_view()),
    path("/received/<uuid:pk>", views.ReceivedDetail.as_view()),
    path("/received/<uuid:pk>/rows/<uuid:row>", views.DecideRow.as_view()),
]
