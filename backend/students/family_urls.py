"""A guardian's children, under family/ on an institution's own host."""

from django.urls import path

from attendance.views import ChildAttendance
from fees.views import ChildFees, ChildOrder
from students import family

urlpatterns = [
    path("children", family.Children.as_view()),
    path("children/<uuid:pk>", family.Child.as_view()),
    path("children/<uuid:pk>/attendance", ChildAttendance.as_view()),
    path("children/<uuid:pk>/fees", ChildFees.as_view()),
    path("children/<uuid:pk>/fees/orders", ChildOrder.as_view()),
]
