"""Admissions for staff, under institution/admissions/ on an institution's own host."""

from django.urls import path

from admissions import cycle_views, staff_views

urlpatterns = [
    path("cycles", cycle_views.CycleList.as_view()),
    path("cycles/<uuid:pk>", cycle_views.CycleDetail.as_view()),
    path("cycles/<uuid:pk>/publish", cycle_views.Publish.as_view()),
    path("cycles/<uuid:pk>/close", cycle_views.Close.as_view()),
    path("applications", staff_views.ApplicationList.as_view()),
    path("applications/<uuid:pk>", staff_views.ApplicationDetail.as_view()),
    path("applications/<uuid:pk>/start-review", staff_views.StartReview.as_view()),
    path("applications/<uuid:pk>/request-information", staff_views.RequestInformation.as_view()),
    path("applications/<uuid:pk>/eligible", staff_views.Eligible.as_view()),
    path("applications/<uuid:pk>/reject", staff_views.Reject.as_view()),
    path("applications/<uuid:pk>/offer", staff_views.MakeOffer.as_view()),
    path("applications/<uuid:pk>/enroll", staff_views.EnrollView.as_view()),
    path("applications/<uuid:pk>/notes", staff_views.Notes.as_view()),
    path("applications/<uuid:pk>/documents/<uuid:doc>", staff_views.DocumentView.as_view()),
    path("applications/<uuid:pk>/documents/<uuid:doc>/verify", staff_views.VerifyDocument.as_view()),
    path("applications/<uuid:pk>/documents/<uuid:doc>/reject", staff_views.RejectDocument.as_view()),
]
