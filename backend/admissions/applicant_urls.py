"""An applicant's own applications, under applicant/ on an institution's own host."""

from django.urls import path

from admissions import applicant_views as views

urlpatterns = [
    path("applications", views.ApplicationList.as_view()),
    path("applications/<uuid:pk>", views.ApplicationDetail.as_view()),
    path("applications/<uuid:pk>/submit", views.Submit.as_view()),
    path("applications/<uuid:pk>/withdraw", views.Withdraw.as_view()),
    path("applications/<uuid:pk>/accept", views.Accept.as_view()),
]
