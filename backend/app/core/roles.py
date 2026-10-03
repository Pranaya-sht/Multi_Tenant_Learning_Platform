from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPER_VIEWER = "super_viewer"
    TENANT_ADMIN = "tenant_admin"
    TENANT_USER = "tenant_user"


PLATFORM_ROLES = {Role.SUPER_ADMIN, Role.ADMIN, Role.SUPER_VIEWER}
TENANT_ROLES = {Role.TENANT_ADMIN, Role.TENANT_USER}

# Platform administrators manage tenant metadata, never tenant learning content.
PERMISSIONS = {
    Role.SUPER_ADMIN: {
        "tenants:read",
        "tenants:create",
        "tenants:update",
        "tenants:lifecycle",
        "platform_users:read",
        "platform_users:create",
    },
    Role.ADMIN: {"tenants:read", "tenants:create", "tenants:update", "platform_users:read"},
    Role.SUPER_VIEWER: {"tenants:read", "platform_users:read"},
    Role.TENANT_ADMIN: {"tenant:read", "users:manage", "courses:manage", "assignments:manage"},
    Role.TENANT_USER: {"tenant:read", "courses:assigned", "progress:own"},
}
