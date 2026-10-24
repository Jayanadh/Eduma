"""Leave, staff attendance, pay and payroll, under institution/hr/."""

from django.urls import path

from hr import views

urlpatterns = [
    path("leave-types", views.LeaveTypes.as_view()),
    path("leave", views.Leave.as_view()),
    path("leave/<uuid:pk>/approve", views.LeaveAction.as_view(action="approve")),
    path("leave/<uuid:pk>/reject", views.LeaveAction.as_view(action="reject")),
    path("leave/<uuid:pk>/cancel", views.LeaveAction.as_view(action="cancel")),
    path("attendance", views.Attendance.as_view()),
    path("employees", views.Employees.as_view()),
    path("employees/<uuid:pk>/compensation", views.Pay.as_view()),
    path("payroll", views.Payroll.as_view()),
    path("payroll/<uuid:pk>", views.PayrollDetail.as_view()),
    path("payroll/<uuid:pk>/validate", views.PayrollAction.as_view(action="validate")),
    path("payroll/<uuid:pk>/approve", views.PayrollAction.as_view(action="approve")),
    path("payroll/<uuid:pk>/export", views.PayrollAction.as_view(action="export")),
]
