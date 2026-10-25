"""Tokens never reach the logs (TST-021)."""

import logging


def test_verification_tokens_are_redacted_from_request_logs(world, client_for, caplog):
    handler = logging.getLogger("django.request").handlers[0]
    with caplog.at_level(logging.WARNING, logger="django.request"):
        logging.getLogger("django.request").addHandler(caplog.handler)
        caplog.handler.addFilter(handler.filters[0])
        assert client_for(world.a.slug).get("/api/v1/public/verify/SECRET-TOKEN-123").status_code == 404
    assert caplog.records, "the refusal was logged"
    assert all("SECRET-TOKEN-123" not in r.getMessage() for r in caplog.records)
    assert any("/public/verify/[redacted]" in r.getMessage() for r in caplog.records)
