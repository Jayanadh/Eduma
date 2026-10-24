"""A teacher's own classes, under teaching/ on an institution's own host."""

from django.urls import path

from academics import teaching, timetable_views
from attendance import views as attendance

urlpatterns = [
    path("classes", teaching.Classes.as_view()),
    path("classes/<uuid:section>/students", teaching.ClassRoster.as_view()),
    path("offerings/<uuid:offering>/students", teaching.OfferingRoster.as_view()),
    path("day", timetable_views.Day.as_view()),
    path("attendance", attendance.OpenSession.as_view()),
    path("attendance/<uuid:pk>", attendance.SessionDetail.as_view()),
    path("attendance/<uuid:pk>/marks", attendance.SaveMarks.as_view()),
    path("attendance/<uuid:pk>/submit", attendance.SubmitSession.as_view()),
    path("attendance/marks/<uuid:mark>/corrections", attendance.RequestCorrection.as_view()),
    path("assignments", attendance.TeachingAssignments.as_view()),
    path("assignments/<uuid:pk>", attendance.TeachingAssignment.as_view()),
    path("submissions/<uuid:pk>/feedback", attendance.Feedback.as_view()),
]
