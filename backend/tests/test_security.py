from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.security import create_access_token, decode_access_token


def test_signed_token_preserves_subject_and_tenant(settings):
    token = create_access_token("user-a", settings, tenant_id="tenant-a")
    claims = decode_access_token(token, settings)
    assert claims.sub == "user-a"
    assert claims.tenant_id == "tenant-a"
    assert claims.exp > claims.iat


def test_wrong_signing_key_is_rejected(settings):
    token = create_access_token("user-a", settings)
    other_settings = settings.model_copy(update={"jwt_audience": "other-api"})
    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(token, other_settings)

    payload = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(payload, "another-secret-at-least-thirty-two-characters", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged, settings)


@pytest.mark.parametrize("mutation", ["expired", "wrong_type", "missing_subject", "wrong_issuer"])
def test_invalid_claims_are_rejected(settings, mutation):
    payload = jwt.decode(
        create_access_token("user-a", settings), options={"verify_signature": False}
    )
    if mutation == "expired":
        payload["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    elif mutation == "wrong_type":
        payload["type"] = "refresh"
    elif mutation == "wrong_issuer":
        payload["iss"] = "another-issuer"
    else:
        del payload["sub"]
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises((jwt.InvalidTokenError, ValidationError)):
        decode_access_token(token, settings)


def test_empty_token_subject_is_rejected(settings):
    with pytest.raises(ValueError):
        create_access_token(" ", settings)
