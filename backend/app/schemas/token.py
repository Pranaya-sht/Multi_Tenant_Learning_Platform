from typing import Literal

from pydantic import BaseModel, Field


class TokenClaims(BaseModel):
    sub: str = Field(min_length=1)
    iat: int
    exp: int
    iss: str
    aud: str
    type: Literal["access"]
    tenant_id: str | None = None
    ver: int = Field(default=0, ge=0)
