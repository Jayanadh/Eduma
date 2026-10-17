from django.http import Http404
from rest_framework.exceptions import NotAuthenticated, Throttled, ValidationError

from common.exceptions import VersionConflict, problem_handler


def test_health(api):
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
