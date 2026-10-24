"""Attendance for managers, under institution/attendance/."""

from django.urls import path

from attendance import views

urlpatterns = [
    path("corrections", views.Corrections.as_view()),
    path("corrections/<uuid:pk>/approve", views.DecideCorrection.as_view(approve=True)),
    path("corrections/<uuid:pk>/reject", views.DecideCorrection.as_view(approve=False)),
    path("sessions/<uuid:pk>/lock", views.Lock.as_view()),
]
