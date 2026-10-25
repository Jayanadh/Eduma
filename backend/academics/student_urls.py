"""A student's own academic pages, under student/ on their institution's host."""

from django.urls import path

from academics import registration_views
from attendance import views as attendance
from campus import views as campus
from development import views as development
from fees import views as fees
from results import views as results

urlpatterns = [
    path("registration", registration_views.OwnRegistration.as_view()),
    path("registrations/<uuid:pk>/drop", registration_views.OwnDrop.as_view()),
    path("progress", registration_views.OwnProgress.as_view()),
    path("attendance", attendance.OwnAttendance.as_view()),
    path("assignments", attendance.OwnAssignments.as_view()),
    path("assignments/<uuid:pk>/submit", attendance.HandIn.as_view()),
    path("results", results.OwnResults.as_view()),
    path("documents", results.OwnDocuments.as_view()),
    path("fees", fees.OwnFees.as_view()),
    path("fees/orders", fees.OwnOrder.as_view()),
    path("campus", campus.OwnCampus.as_view()),
    path("campus/out-passes", campus.OwnOutPass.as_view()),
    path("placements", development.OwnPlacements.as_view()),
    path("placements/<uuid:pk>/apply", development.OwnApply.as_view()),
    path("placement-applications/<uuid:pk>/decide", development.OwnDecide.as_view()),
    path("alumni", development.OwnAlumni.as_view()),
    path("research", development.OwnResearch.as_view()),
    path("research/milestones/<uuid:pk>/submit", development.OwnMilestone.as_view()),
]
