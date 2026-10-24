"""Library, transport and hostel, under institution/campus/."""

from django.urls import path

from campus import views

urlpatterns = [
    path("titles", views.Titles.as_view()),
    path("loans", views.Loans.as_view()),
    path("loans/<uuid:pk>/return", views.LoanAction.as_view(action="return")),
    path("loans/<uuid:pk>/renew", views.LoanAction.as_view(action="renew")),
    path("loans/<uuid:pk>/lost", views.LoanAction.as_view(action="lost")),
    path("reservations", views.Reservations.as_view()),
    path("fines/<uuid:pk>/waive", views.Waive.as_view()),
    path("vehicles", views.Vehicles.as_view()),
    path("routes", views.Routes.as_view()),
    path("riders", views.Riders.as_view()),
    path("pickups", views.Pickups.as_view()),
    path("trips", views.Trips.as_view()),
    path("trips/<uuid:pk>/state", views.TripAction.as_view(action="state")),
    path("trips/<uuid:pk>/board", views.TripAction.as_view(action="board")),
    path("trips/<uuid:pk>/drop", views.TripAction.as_view(action="drop")),
    path("hostels", views.Hostels.as_view()),
    path("hostels/<uuid:pk>", views.HostelDetail.as_view()),
    path("hostels/<uuid:pk>/beds", views.Beds.as_view()),
    path("allocations", views.Allocations.as_view()),
    path("allocations/<uuid:pk>/approve", views.AllocationAction.as_view(action="approve")),
    path("allocations/<uuid:pk>/check-in", views.AllocationAction.as_view(action="check-in")),
    path("allocations/<uuid:pk>/check-out", views.AllocationAction.as_view(action="check-out")),
    path("allocations/<uuid:pk>/reject", views.AllocationAction.as_view(action="reject")),
    path("allocations/<uuid:pk>/transfer", views.AllocationAction.as_view(action="transfer")),
    path("out-passes", views.OutPasses.as_view()),
    path("out-passes/<uuid:pk>/approve", views.OutPassAction.as_view(action="approve")),
    path("out-passes/<uuid:pk>/reject", views.OutPassAction.as_view(action="reject")),
    path("out-passes/<uuid:pk>/returned", views.OutPassAction.as_view(action="returned")),
]
