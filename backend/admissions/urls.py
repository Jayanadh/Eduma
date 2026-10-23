"""Admissions for staff, under institution/admissions/ on an institution's own host."""

from django.urls import path

from admissions import cycle_views, enquiry_views, staff_views

urlpatterns = [
    path("cycles", cycle_views.CycleList.as_view()),
    path("cycles/<uuid:pk>", cycle_views.CycleDetail.as_view()),
    path("cycles/<uuid:pk>/publish", cycle_views.Publish.as_view()),
    path("cycles/<uuid:pk>/close", cycle_views.Close.as_view()),
    path("enquiries", enquiry_views.EnquiryList.as_view()),
    path("enquiries/assignees", enquiry_views.Assignees.as_view()),
    path("enquiries/<uuid:pk>", enquiry_views.EnquiryDetail.as_view()),
    path("enquiries/<uuid:pk>/follow-ups", enquiry_views.FollowUps.as_view()),
    path("enquiries/<uuid:pk>/convert", enquiry_views.Convert.as_view()),
    path("enquiries/<uuid:pk>/close", enquiry_views.Close.as_view()),
    path("enquiries/<uuid:pk>/reopen", enquiry_views.Reopen.as_view()),
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
