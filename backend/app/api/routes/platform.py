from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import Db, permit
from app.core.roles import Role
from app.core.security import hash_password
from app.models import Tenant, User
from app.schemas.domain import (
    PlatformUserCreate,
    ReactivateInput,
    TenantCreate,
    TenantOut,
    TenantUpdate,
    UserOut,
)
from app.services.common import commit
from app.services.tenants import effective_status

router = APIRouter(tags=["platform administration"])
ReadTenants = Annotated[User, Depends(permit("tenants:read"))]
CreateTenants = Annotated[User, Depends(permit("tenants:create"))]
UpdateTenants = Annotated[User, Depends(permit("tenants:update"))]
Lifecycle = Annotated[User, Depends(permit("tenants:lifecycle"))]
ReadPlatformUsers = Annotated[User, Depends(permit("platform_users:read"))]
CreatePlatformUsers = Annotated[User, Depends(permit("platform_users:create"))]


def tenant_output(tenant: Tenant) -> TenantOut:
    result = TenantOut.model_validate(tenant)
    result.status = effective_status(tenant)
    return result


def find_tenant(db: Db, identifier: UUID, *, lock: bool = False) -> Tenant:
    query = select(Tenant).where(Tenant.id == str(identifier))
    if lock:
        query = query.with_for_update()
    tenant = db.scalar(query)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    return tenant


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(
    user: ReadTenants,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return [
        tenant_output(t)
        for t in db.scalars(
            select(Tenant).order_by(Tenant.created_at, Tenant.id).limit(limit).offset(offset)
        )
    ]


@router.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(data: TenantCreate, user: CreateTenants, db: Db, request: Request):
    now = datetime.now(UTC)
    tenant = Tenant(
        name=data.name,
        slug=data.slug,
        created_at=now,
        trial_expires_at=now + timedelta(days=request.app.state.settings.trial_days),
        status="created",
    )
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Tenant slug already exists") from exc
    db.add(
        User(
            tenant_id=tenant.id,
            email=str(data.admin.email),
            name=data.admin.name,
            password_hash=hash_password(data.admin.password),
            role=Role.TENANT_ADMIN,
        )
    )
    tenant.status = "trial_active"
    commit(db)
    return tenant_output(tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: UUID, user: ReadTenants, db: Db):
    return tenant_output(find_tenant(db, tenant_id))


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: UUID, data: TenantUpdate, user: UpdateTenants, db: Db):
    tenant = find_tenant(db, tenant_id, lock=True)
    tenant.name = data.name
    commit(db)
    return tenant_output(tenant)


@router.post("/tenants/{tenant_id}/reactivate", response_model=TenantOut)
def reactivate(tenant_id: UUID, data: ReactivateInput, user: Lifecycle, db: Db):
    tenant = find_tenant(db, tenant_id, lock=True)
    tenant.trial_expires_at = datetime.now(UTC) + timedelta(days=data.days)
    tenant.status = "trial_active"
    commit(db)
    return tenant_output(tenant)


@router.post("/tenants/{tenant_id}/expire", response_model=TenantOut)
def expire(tenant_id: UUID, user: Lifecycle, db: Db):
    tenant = find_tenant(db, tenant_id, lock=True)
    tenant.trial_expires_at = datetime.now(UTC)
    tenant.status = "expired"
    commit(db)
    return tenant_output(tenant)


@router.get("/platform-users", response_model=list[UserOut])
def list_platform_users(
    user: ReadPlatformUsers,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return list(
        db.scalars(
            select(User)
            .where(User.tenant_id.is_(None))
            .order_by(User.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/platform-users", response_model=UserOut, status_code=201)
def create_platform_user(data: PlatformUserCreate, user: CreatePlatformUsers, db: Db):
    new_user = User(
        email=str(data.email),
        name=data.name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(new_user)
    commit(db)
    return new_user
