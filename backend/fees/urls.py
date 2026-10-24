"""Fees, under institution/fees/."""

from django.urls import path

from fees import views

urlpatterns = [
    path("heads", views.Heads.as_view()),
    path("plans", views.Plans.as_view()),
    path("plans/<uuid:pk>/publish", views.PlanAction.as_view(action="publish")),
    path("plans/<uuid:pk>/revise", views.PlanAction.as_view(action="revise")),
    path("students/<uuid:pk>/invoices", views.StudentInvoices.as_view()),
    path("students/<uuid:pk>/statement", views.Statement.as_view()),
    path("invoices/<uuid:pk>", views.InvoiceDetail.as_view()),
    path("credit-notes", views.CreditNotes.as_view()),
    path("credit-notes/<uuid:pk>/approve", views.DecideCredit.as_view(approve=True)),
    path("credit-notes/<uuid:pk>/reject", views.DecideCredit.as_view(approve=False)),
    path("payments", views.Payments.as_view()),
    path("refunds", views.Refunds.as_view()),
    path("refunds/<uuid:pk>/approve", views.RefundAction.as_view(action="approve")),
    path("refunds/<uuid:pk>/reject", views.RefundAction.as_view(action="reject")),
    path("refunds/<uuid:pk>/complete", views.RefundAction.as_view(action="complete")),
    path("refunds/<uuid:pk>/fail", views.RefundAction.as_view(action="fail")),
    path("provider", views.ProviderView.as_view()),
    path("orders", views.Orders.as_view()),
    path("settlements", views.Settlements.as_view()),
    path("cases", views.Cases.as_view()),
    path("cases/<uuid:pk>/resolve", views.Resolve.as_view()),
    path("trial-balance", views.TrialBalance.as_view()),
    path("journal.csv", views.JournalExport.as_view()),
]
