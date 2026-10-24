"""Students, under institution/ on an institution's own host."""

from django.urls import path

from attendance.views import StudentAttendance
from students import views

urlpatterns = [
    path("students", views.StudentList.as_view()),
    path("students/<uuid:pk>", views.StudentDetail.as_view()),
    path("students/<uuid:pk>/history", views.StudentHistory.as_view()),
    path("students/<uuid:pk>/login", views.GiveLogin.as_view()),
    path("students/<uuid:pk>/withdraw", views.Withdraw.as_view()),
    path("students/<uuid:pk>/program", views.StudentProgram.as_view()),
    path("students/<uuid:pk>/attendance", StudentAttendance.as_view()),
    path("students/<uuid:pk>/reinstate", views.Reinstate.as_view()),
    path("students/<uuid:pk>/guardians", views.GuardianList.as_view()),
    path("students/<uuid:pk>/guardians/<uuid:link>/verify", views.GuardianVerify.as_view()),
    path("students/<uuid:pk>/guardians/<uuid:link>/revoke", views.GuardianRevoke.as_view()),
]
