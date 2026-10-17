from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import Membership, User, normalize_username
from accounts.serializers import ChangePasswordSerializer, LoginSerializer, MeSerializer
from accounts.throttles import LoginIdThrottle
from common import audit
from common.exceptions import Problem
from institutions.models import SIGN_IN_STATES

REFUSED = "Invalid login ID or password."
SWITCHED_OFF = "Your login is switched off. Contact your administrator."


def may_sign_in_here(request, user: User) -> bool:
    """The platform host admits platform admins; an institution's host admits its members while it is set up or
    active. Nobody signs in on an unknown host. (authenticate() has already refused switched-off logins.)"""
    if request.site_kind == "platform":
        return user.is_platform_admin
    if request.site_kind == "institution":
        institution = request.institution
        return institution.lifecycle_status in SIGN_IN_STATES and institution.memberships.filter(
            user=user, status=Membership.Status.ACTIVE
        ).exists()
    return False


def _me(request, user):
    return MeSerializer(user, context={"request": request}).data


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(APIView):
    """Sets the CSRF cookie and tells the app who, if anyone, is signed in on this host."""

    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response({"user": _me(request, user) if user else None})


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, LoginIdThrottle]
    throttle_scope = "login"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # DRF checks CSRF only for a signed-in session. Signing in needs it too, or another site could sign a visitor
        # in as the attacker without them noticing. The app gets the token from the session call first.
        SessionAuthentication().enforce_csrf(request)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = normalize_username(serializer.validated_data["username"])
        password = serializer.validated_data["password"]
        user = authenticate(request, username=username, password=password)
        if user is None or not may_sign_in_here(request, user):
            # Explain a switched-off login only to someone who knows its password and could otherwise sign in here.
            off = User.objects.filter(username=username, is_active=False).first()
            if user is None and off is not None and off.check_password(password) and may_sign_in_here(request, off):
                raise Problem(400, "login_switched_off", SWITCHED_OFF)
            raise Problem(400, "invalid_credentials", REFUSED)
        login(request, user)
        request.session["site"] = request.site_key
        audit.log(user, "auth.login", user, f"{user.full_name} signed in", institution=request.institution)
        return Response({"user": _me(request, user)})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    # Slows down guessing the current password from a session left open on someone else's device.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            raise Problem(400, "wrong_password", "Current password is incorrect.")
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save()
        # This browser stays signed in; every other one now has to sign in with the new password.
        update_session_auth_hash(request, user)
        request.session["site"] = request.site_key
        audit.log(user, "auth.password_changed", user, f"{user.full_name} changed their password",
                  institution=request.institution)
        return Response(status=status.HTTP_204_NO_CONTENT)
