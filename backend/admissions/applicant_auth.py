"""Applicants make their own account at the institution's address (slice 4a S4-02). It can only apply: its membership
is of kind applicant, with no staff or student access."""

from django.contrib.auth import login, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import Membership, User, validate_username
from accounts.views import _me
from common import audit
from configuration.gates import require_module
from institutions.models import SIGN_IN_STATES


class SignupInput(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class SignupView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        SessionAuthentication().enforce_csrf(request)  # as for signing in: no cross-site sign-ups

    def post(self, request):
        if request.site_kind != "institution":
            raise NotFound()
        institution = request.institution
        require_module(institution, "admissions")
        if institution.lifecycle_status not in SIGN_IN_STATES:
            raise PermissionDenied("Applications are not being taken here right now.")
        data = SignupInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        try:
            username = validate_username(values["username"])
        except DjangoValidationError as error:
            raise ValidationError({"username": error.messages}) from error
        if User.objects.filter(username=username).exists():
            raise ValidationError({"username": ["This login ID is already in use. Choose another, or sign in."]})
        person = User(username=username, full_name=values["full_name"], email=values["email"], mobile=values["phone"])
        try:
            password_validation.validate_password(values["password"], person)
        except DjangoValidationError as error:
            raise ValidationError({"password": error.messages}) from error
        person.set_password(values["password"])
        with transaction.atomic():
            person.save()
            Membership.objects.create(institution=institution, user=person, kind=Membership.Kind.APPLICANT)
            audit.log(
                person,
                "applicant.signed_up",
                person,
                f"{person.full_name} made an applicant account",
                institution=institution,
            )
        login(request, person, backend="django.contrib.auth.backends.ModelBackend")
        request.session["site"] = request.site_key
        return Response({"user": _me(request, person)}, status=status.HTTP_201_CREATED)
