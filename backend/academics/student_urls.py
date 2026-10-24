"""A student's own academic pages, under student/ on their institution's host."""

from django.urls import path

from academics import registration_views
from attendance import views as attendance

urlpatterns = [
    path("registration", registration_views.OwnRegistration.as_view()),
    path("registrations/<uuid:pk>/drop", registration_views.OwnDrop.as_view()),
    path("progress", registration_views.OwnProgress.as_view()),
    path("attendance", attendance.OwnAttendance.as_view()),
    path("assignments", attendance.OwnAssignments.as_view()),
    path("assignments/<uuid:pk>/submit", attendance.HandIn.as_view()),
]
