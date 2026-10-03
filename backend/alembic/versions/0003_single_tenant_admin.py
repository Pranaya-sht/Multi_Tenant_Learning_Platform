"""Limit each institute to one Tenant Admin account."""

import sqlalchemy as sa

from alembic import op

revision = "0003_single_tenant_admin"
down_revision = "f1fa000f70dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT tenant_id, count(*) AS total FROM users "
                "WHERE role = 'tenant_admin' GROUP BY tenant_id HAVING count(*) > 1"
            )
        )
        .first()
    )
    if duplicates:
        raise RuntimeError(
            "Migration requires one Tenant Admin per institute. "
            f"Institute {duplicates.tenant_id} has {duplicates.total}; "
            "choose the account to keep and demote the others before retrying."
        )
    missing = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT t.id FROM tenants AS t LEFT JOIN users AS u "
                "ON u.tenant_id = t.id AND u.role = 'tenant_admin' AND u.is_active = true "
                "WHERE u.id IS NULL LIMIT 1"
            )
        )
        .first()
    )
    if missing:
        raise RuntimeError(
            "Migration requires one active Tenant Admin per institute. "
            f"Institute {missing.id} has none; restore an administrator before retrying."
        )
    op.create_index(
        "uq_users_one_tenant_admin",
        "users",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("role = 'tenant_admin'"),
        sqlite_where=sa.text("role = 'tenant_admin'"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_one_tenant_admin", table_name="users")
