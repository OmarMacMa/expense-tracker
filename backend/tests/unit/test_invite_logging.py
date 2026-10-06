from app.middleware.logging import safe_request_path


def test_invite_secrets_are_not_logged() -> None:
    assert safe_request_path("/api/v1/spaces/join/secret") == (
        "/api/v1/spaces/join/[redacted]"
    )
    assert safe_request_path("/api/v1/spaces/invites/secret/preview") == (
        "/api/v1/spaces/invites/[redacted]/preview"
    )
    assert safe_request_path("/api/v1/spaces/space-id/membership-transfers") == (
        "/api/v1/spaces/space-id/membership-transfers"
    )
