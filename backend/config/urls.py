from django.conf import settings
from django.contrib import admin
from django.urls import path

from common.views import health

urlpatterns = [
    path("api/v1/health", health, name="health"),
]

if settings.ADMIN_ENABLED:
    urlpatterns.append(path("admin/", admin.site.urls))
