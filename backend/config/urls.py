from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from accounts.views import ChangePasswordView, LoginView, LogoutView, SessionView
from admissions.applicant_auth import SignupView
from admissions.enquiry_views import PublicEnquiry
from admissions.public import public_admissions
from affiliations.views import ConsoleGrants
from common.views import AuditEventList, health
from institutions.urls import platform_patterns
from institutions.views import OwnInstitutionView, module_catalogue, platform_overview
from sites.public import PublicSiteView, public_asset
from sites.urls import site_patterns
from students.views import OwnRecord

urlpatterns = [
    path("api/v1/health", health, name="health"),
    path("api/v1/session", SessionView.as_view(), name="session"),
    path("api/v1/session/login", LoginView.as_view(), name="session-login"),
    path("api/v1/session/logout", LogoutView.as_view(), name="session-logout"),
    path("api/v1/session/change-password", ChangePasswordView.as_view(), name="session-change-password"),
    path("api/v1/public/site", PublicSiteView.as_view(), name="public-site"),
    path("api/v1/public/assets/<uuid:asset_id>", public_asset, name="public-asset"),
    path("api/v1/public/admissions", public_admissions, name="public-admissions"),
    path("api/v1/public/enquiries", PublicEnquiry.as_view(), name="public-enquiries"),
    path("api/v1/applicant/signup", SignupView.as_view(), name="applicant-signup"),
    path("api/v1/applicant/", include("admissions.applicant_urls")),
    path("api/v1/institution/site/", include(site_patterns)),
    path("api/v1/institution/", include("organization.urls")),
    path("api/v1/institution/", include("accounts.urls")),
    path("api/v1/institution/", include("configuration.urls")),
    path("api/v1/institution/admissions/", include("admissions.urls")),
    path("api/v1/institution/", include("students.urls")),
    path("api/v1/institution/imports", include("imports.urls")),
    path("api/v1/institution/academics/", include("academics.urls")),
    path("api/v1/institution/affiliations", include("affiliations.urls")),
    path("api/v1/institution/attendance/", include("attendance.urls")),
    path("api/v1/teaching/", include("academics.teaching_urls")),
    path("api/v1/student/me", OwnRecord.as_view(), name="student-me"),
    path("api/v1/student/", include("academics.student_urls")),
    path("api/v1/family/", include("students.family_urls")),
    path("api/v1/institution", OwnInstitutionView.as_view(), name="own-institution"),
    path("api/v1/platform/overview", platform_overview, name="platform-overview"),
    path("api/v1/platform/modules", module_catalogue, name="platform-modules"),
    path("api/v1/platform/audit", AuditEventList.as_view(), name="platform-audit"),
    path("api/v1/platform/affiliations", ConsoleGrants.as_view(), name="platform-affiliations"),
    path("api/v1/platform/institutions/<uuid:institution_id>/audit", AuditEventList.as_view()),
    path("api/v1/platform/", include(platform_patterns)),
]

if settings.ADMIN_ENABLED:
    urlpatterns.append(path("admin/", admin.site.urls))
