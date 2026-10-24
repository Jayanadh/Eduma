"""Communication, under communication/ on an institution's own host."""

from django.urls import path

from communication import views

urlpatterns = [
    path("conversations", views.Conversations.as_view()),
    path("conversations/<uuid:pk>", views.ConversationDetail.as_view()),
    path("conversations/<uuid:pk>/messages", views.Messages.as_view()),
    path("conversations/<uuid:pk>/read", views.Read.as_view()),
    path("contacts", views.Contacts.as_view()),
    path("notifications", views.Notifications.as_view()),
    path("preferences", views.Preferences.as_view()),
    path("policy", views.PolicyView.as_view()),
    path("media", views.MediaView.as_view()),
    path("media/verify", views.Verify.as_view()),
    path("calls", views.Calls.as_view()),
    path("calls/<uuid:pk>", views.CallDetail.as_view()),
    path("calls/<uuid:pk>/accept", views.CallAction.as_view(action="accept")),
    path("calls/<uuid:pk>/decline", views.CallAction.as_view(action="decline")),
    path("calls/<uuid:pk>/cancel", views.CallAction.as_view(action="cancel")),
    path("calls/<uuid:pk>/end", views.CallAction.as_view(action="end")),
    path("classes", views.Classes.as_view()),
    path("classes/<uuid:pk>", views.ClassDetail.as_view()),
    path("classes/<uuid:pk>/join", views.Join.as_view()),
    path("classes/<uuid:pk>/leave", views.Leave.as_view()),
    path("classes/<uuid:pk>/end", views.HostAction.as_view(action="end")),
    path("classes/<uuid:pk>/participants/<uuid:participant>/admit", views.HostAction.as_view(action="admit")),
    path("classes/<uuid:pk>/participants/<uuid:participant>/remove", views.HostAction.as_view(action="remove")),
]
