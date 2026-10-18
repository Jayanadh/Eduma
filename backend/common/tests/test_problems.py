from django.http import Http404
from rest_framework.exceptions import NotAuthenticated, Throttled, ValidationError

from common.exceptions import VersionConflict, problem_handler


def test_health(api, db):  # an unknown host is looked up as a custom domain
    assert api.get("/api/v1/health").json() == {"status": "ok"}


def test_validation_error_is_422_problem():
    response = problem_handler(ValidationError({"slug": ["Bad."], "admin": {"username": ["Taken."]}}), {})
    assert response.status_code == 422
    assert response.content_type == "application/problem+json"
    assert response.data["code"] == "validation_failed"
    assert response.data["detail"] == "Bad."
    assert {"field": "admin.username", "code": "invalid", "message": "Taken."} in response.data["errors"]


def test_non_field_errors_have_an_empty_field():
    response = problem_handler(ValidationError({"non_field_errors": ["Whole request."]}), {})
    assert response.data["errors"] == [{"field": "", "code": "invalid", "message": "Whole request."}]


def test_not_authenticated_is_403_authentication_required():
    response = problem_handler(NotAuthenticated(), {})
    assert response.status_code == 403
    assert response.data["code"] == "authentication_required"


def test_version_conflict_carries_current_version():
    data = problem_handler(VersionConflict(8), {}).data
    assert (data["status"], data["code"], data["current_version"]) == (409, "version_conflict", 8)
    assert data["type"] == "urn:eduma:problem:version_conflict"
    assert data["title"] == "This record changed"


def test_http404_is_not_found_and_throttled_is_rate_limited():
    assert problem_handler(Http404(), {}).data["code"] == "not_found"
    throttled = problem_handler(Throttled(wait=5), {})
    assert throttled.data["code"] == "rate_limited"
    assert throttled["Retry-After"] == "5"


def test_unknown_exceptions_fall_through():
    assert problem_handler(ValueError("boom"), {}) is None


def test_django_validation_error_is_422_problem():
    """A model-level check (such as a malformed id in a filter) is the caller's mistake, not a server error."""
    from django.core.exceptions import ValidationError as DjangoValidationError

    response = problem_handler(DjangoValidationError("“nope” is not a valid UUID."), {})
    assert response.status_code == 422
    assert response.data["code"] == "validation_failed"


def test_integrity_error_is_409_problem():
    """Two identical saves at the same instant: the loser is told to reload, not shown a server error."""
    from django.db import IntegrityError

    response = problem_handler(IntegrityError("duplicate key value"), {})
    assert response.status_code == 409
    assert response.data["code"] == "conflict"
    assert "duplicate key" not in response.data["detail"]


def test_malformed_campus_filter_is_422(world, client_for):
    response = client_for(world.a.slug, world.a_admin).get("/api/v1/institution/departments", {"campus": "garbage"})
    assert response.status_code == 422
