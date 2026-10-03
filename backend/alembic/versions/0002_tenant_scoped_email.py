"""Allow separate accounts with the same email in different tenants."""

import sqlalchemy as sa

from alembic import context, op

revision = "0002_tenant_scoped_email"
down_revision = "0001_learning_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_email", type_="unique")
        batch.create_unique_constraint("uq_users_tenant_id_email", ["tenant_id", "email"])
    op.create_index(
        "uq_users_platform_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
        sqlite_where=sa.text("tenant_id IS NULL"),
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        duplicate = op.get_bind().scalar(
            sa.text("SELECT email FROM users GROUP BY email HAVING count(*) > 1 LIMIT 1")
        )
        if duplicate is not None:
            raise RuntimeError(
                "Cannot restore globally unique emails while cross-scope duplicates exist. "
                "Resolve those accounts explicitly before downgrading; no data was removed."
            )
    op.drop_index("uq_users_platform_email", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_tenant_id_email", type_="unique")
        batch.create_unique_constraint("uq_users_email", ["email"])
