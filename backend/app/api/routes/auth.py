from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import or_, select, update

from app.api.dependencies import CurrentUser, Db
from app.core.roles import PERMISSIONS, Role
from app.core.security import create_access_token, dummy_hash, verify_password
from app.models import Tenant, User
from app.schemas.domain import InstituteSuggestion, LoginInput, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/institutes", response_model=list[InstituteSuggestion])
def search_institutes(db: Db, q: Annotated[str, Query(min_length=2, max_length=80)]):
    # Return only public institute identity; login still validates the account and slug.
    term = q.strip()
    if len(term) < 2:
        return []
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return [
        InstituteSuggestion(name=name, slug=slug)
        for name, slug in db.execute(
            select(Tenant.name, Tenant.slug)
            .where(
                or_(
                    Tenant.name.ilike(pattern, escape="\\"),
                    Tenant.slug.ilike(pattern, escape="\\"),
                )
            )
            .order_by(Tenant.name, Tenant.slug)
            .limit(10)
        )
    ]


@router.post("/login", response_model=TokenOut)
def login(data: LoginInput, db: Db, request: Request, response: Response):
    query = select(User).where(User.email == str(data.email))
    if data.tenant_slug is None:
        query = query.where(User.tenant_id.is_(None))
    else:
        query = query.join(Tenant, User.tenant_id == Tenant.id).where(
            Tenant.slug == data.tenant_slug
        )
    user = db.scalar(query)
    valid = verify_password(data.password, user.password_hash if user else dummy_hash)
    if not valid or user is None or not user.is_active:
        raise HTTPException(
            401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    settings = request.app.state.settings
    response.headers["Cache-Control"] = "no-store"
    return TokenOut(
        access_token=create_access_token(
            user.id, settings, tenant_id=user.tenant_id, version=user.token_version
        ),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.get("/permissions", response_model=list[str])
def permissions(user: CurrentUser):
    return sorted(PERMISSIONS[Role(user.role)])


@router.post("/logout", status_code=204)
def logout(user: CurrentUser, db: Db):
    db.execute(update(User).where(User.id == user.id).values(token_version=User.token_version + 1))
    db.commit()
    return Response(status_code=204)
