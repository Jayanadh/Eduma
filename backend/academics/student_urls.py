"""A student's own academic pages, under student/ on their institution's host."""

from django.urls import path

from academics import registration_views

urlpatterns = [
    path("registration", registration_views.OwnRegistration.as_view()),
    path("registrations/<uuid:pk>/drop", registration_views.OwnDrop.as_view()),
]
