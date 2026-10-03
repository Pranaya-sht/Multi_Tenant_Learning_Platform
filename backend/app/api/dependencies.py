from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import PERMISSIONS, TENANT_ROLES, Role
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Tenant, User
from app.services.tenants import effective_status

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        401, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials, request.app.state.settings)
        identifier = str(UUID(claims.sub))
    except (jwt.InvalidTokenError, ValidationError, ValueError) as exc:
        raise unauthorized from exc
    user = db.get(User, identifier)
    if user is None or not user.is_active or claims.ver != user.token_version:
        raise unauthorized
    if claims.tenant_id != user.tenant_id:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def permit(permission: str):
    def check(user: CurrentUser) -> User:
        if permission not in PERMISSIONS[Role(user.role)]:
            raise HTTPException(403, "Insufficient permissions")
        return user

    return check


def tenant_identity(user: CurrentUser, db: Db) -> User:
    if Role(user.role) not in TENANT_ROLES:
        raise HTTPException(403, "Tenant account required")
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(401, "Tenant unavailable")
    return user


TenantIdentity = Annotated[User, Depends(tenant_identity)]


def learning_user(user: CurrentUser, db: Db) -> User:
    if Role(user.role) not in TENANT_ROLES:
        raise HTTPException(403, "Tenant account required")
    authenticated_version = user.token_version
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == user.tenant_id)
        .with_for_update(read=user.role == Role.TENANT_USER)
        .execution_options(populate_existing=True)
    )
    if tenant is None:
        raise HTTPException(401, "Tenant unavailable")
    if effective_status(tenant) != "trial_active":
        raise HTTPException(403, "Tenant trial expired; contact the platform administrator")
    # An administrator may have changed this account while we waited for the tenant lock.
    db.refresh(user)
    if not user.is_active or user.token_version != authenticated_version:
        raise HTTPException(401, "Credentials revoked", headers={"WWW-Authenticate": "Bearer"})
    return user


LearningUser = Annotated[User, Depends(learning_user)]


def tenant_admin(user: LearningUser) -> User:
    if user.role != Role.TENANT_ADMIN:
        raise HTTPException(403, "Tenant administrator required")
    return user


TenantAdmin = Annotated[User, Depends(tenant_admin)]
