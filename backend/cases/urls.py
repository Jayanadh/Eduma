"""Service cases, under service-cases/."""

from django.urls import path

from cases import views

urlpatterns = [
    path("", views.Cases.as_view()),
    path("<uuid:pk>", views.CaseDetail.as_view()),
    path("<uuid:pk>/notes", views.Notes.as_view()),
    path("<uuid:pk>/assign", views.Assign.as_view()),
    path("<uuid:pk>/officers", views.Officers.as_view()),
    path("<uuid:pk>/resolve", views.Resolve.as_view()),
    path("<uuid:pk>/appeals", views.Appeals.as_view()),
]
