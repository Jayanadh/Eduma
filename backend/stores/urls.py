"""Procurement, stock, assets and lab booking, under institution/stores/."""

from django.urls import path

from stores import views

urlpatterns = [
    path("rules", views.Rules.as_view()),
    path("suppliers", views.Suppliers.as_view()),
    path("items", views.Items.as_view()),
    path("stock", views.Stock.as_view()),
    path("requisitions", views.Requisitions.as_view()),
    path("requisitions/<uuid:pk>/approve", views.RequisitionAction.as_view(action="approve")),
    path("requisitions/<uuid:pk>/reject", views.RequisitionAction.as_view(action="reject")),
    path("requisitions/<uuid:pk>/order", views.RequisitionAction.as_view(action="order")),
    path("requisitions/<uuid:pk>/receive", views.RequisitionAction.as_view(action="receive")),
    path("assets", views.Assets.as_view()),
    path("assets/<uuid:pk>", views.AssetDetail.as_view()),
    path("assets/<uuid:pk>/transfer", views.AssetAction.as_view(action="transfer")),
    path("assets/<uuid:pk>/maintenance", views.AssetAction.as_view(action="maintenance")),
    path("assets/<uuid:pk>/back", views.AssetAction.as_view(action="back")),
    path("assets/<uuid:pk>/dispose", views.AssetAction.as_view(action="dispose")),
    path("bookings", views.Bookings.as_view()),
    path("bookings/<uuid:pk>/cancel", views.CancelBooking.as_view()),
]
