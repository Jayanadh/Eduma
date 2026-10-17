from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from accounts.views import ChangePasswordView, LoginView, LogoutView, SessionView
from common.views import health
from sites.urls import site_patterns

urlpatterns = [
    path("api/v1/health", health, name="health"),
    path("api/v1/session", SessionView.as_view(), name="session"),
    path("api/v1/session/login", LoginView.as_view(), name="session-login"),
    path("api/v1/session/logout", LogoutView.as_view(), name="session-logout"),
    path("api/v1/session/change-password", ChangePasswordView.as_view(), name="session-change-password"),
    path("api/v1/platform/institutions/<uuid:institution_id>/site/", include(site_patterns)),
    path("api/v1/institution/site/", include(site_patterns)),
]

if settings.ADMIN_ENABLED:
    urlpatterns.append(path("admin/", admin.site.urls))
