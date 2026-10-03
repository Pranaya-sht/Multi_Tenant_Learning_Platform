from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.schemas.token import TokenClaims

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("unused-login-timing-placeholder")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(
    subject: str, settings: Settings, *, tenant_id: str | None = None, version: int = 0
) -> str:
    """Sign an access token after the caller authenticates the user."""
    if not subject.strip():
        raise ValueError("Token subject must not be empty")
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": "access",
        "tenant_id": tenant_id,
        "ver": version,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    """Verify the signature and registered claims before validating our payload."""
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "iat", "exp", "iss", "aud", "type"]},
    )
    return TokenClaims.model_validate(payload)
