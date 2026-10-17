from django.http import JsonResponse

# What someone needs to set their own password: who they are, the change itself, a way out, and the public site.
OPEN_WHILE_PASSWORD_MUST_CHANGE = ("/api/v1/session", "/api/v1/health", "/api/v1/public/")
MUST_CHANGE_PASSWORD = "Change your password before you continue."


class PasswordChangeRequiredMiddleware:
    """Until a person replaces a password someone else set, the API answers nothing but the calls needed to change
    it. The app sends them to the change-password page as well, but the server must not rely on that."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and user.must_change_password
            and request.path.startswith("/api/")
            and not request.path.startswith(OPEN_WHILE_PASSWORD_MUST_CHANGE)
        ):
            body = {
                "type": "urn:eduma:problem:password_change_required",
                "title": "Password change required",
                "status": 403,
                "detail": MUST_CHANGE_PASSWORD,
                "code": "password_change_required",
                "errors": [],
            }
            return JsonResponse(body, status=403, content_type="application/problem+json")
        return self.get_response(request)
