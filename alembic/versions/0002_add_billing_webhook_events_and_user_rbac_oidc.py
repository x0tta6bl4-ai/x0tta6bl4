"""Add billing webhook idempotency table and missing user RBAC/OIDC columns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-20 08:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "users"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            if not _column_exists(inspector, "users", "role"):
                batch_op.add_column(
                    sa.Column("role", sa.String(), nullable=True, server_default="user")
                )
            if not _column_exists(inspector, "users", "oidc_id"):
                batch_op.add_column(sa.Column("oidc_id", sa.String(), nullable=True))
            if not _column_exists(inspector, "users", "oidc_provider"):
                batch_op.add_column(sa.Column("oidc_provider", sa.String(), nullable=True))
            if not _column_exists(inspector, "users", "vpn_uuid"):
                batch_op.add_column(sa.Column("vpn_uuid", sa.String(), nullable=True))

    # Refresh inspector after DDL.
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "users"):
        if not _index_exists(inspector, "users", "ix_users_oidc_id"):
            op.create_index("ix_users_oidc_id", "users", ["oidc_id"], unique=True)
        if not _index_exists(inspector, "users", "ix_users_vpn_uuid"):
            op.create_index("ix_users_vpn_uuid", "users", ["vpn_uuid"], unique=True)

    if not _table_exists(inspector, "billing_webhook_events"):
        op.create_table(
            "billing_webhook_events",
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload_hash", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="processing"),
            sa.Column("response_json", sa.Text(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("event_id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "billing_webhook_events"):
        if not _index_exists(
            inspector, "billing_webhook_events", "ix_billing_webhook_events_event_id"
        ):
            op.create_index(
                "ix_billing_webhook_events_event_id",
                "billing_webhook_events",
                ["event_id"],
                unique=False,
            )
        if not _index_exists(
            inspector, "billing_webhook_events", "ix_billing_webhook_events_payload_hash"
        ):
            op.create_index(
                "ix_billing_webhook_events_payload_hash",
                "billing_webhook_events",
                ["payload_hash"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "billing_webhook_events"):
        if _index_exists(
            inspector, "billing_webhook_events", "ix_billing_webhook_events_payload_hash"
        ):
            op.drop_index(
                "ix_billing_webhook_events_payload_hash",
                table_name="billing_webhook_events",
            )
        if _index_exists(
            inspector, "billing_webhook_events", "ix_billing_webhook_events_event_id"
        ):
            op.drop_index(
                "ix_billing_webhook_events_event_id",
                table_name="billing_webhook_events",
            )
        op.drop_table("billing_webhook_events")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "users"):
        if _index_exists(inspector, "users", "ix_users_vpn_uuid"):
            op.drop_index("ix_users_vpn_uuid", table_name="users")
        if _index_exists(inspector, "users", "ix_users_oidc_id"):
            op.drop_index("ix_users_oidc_id", table_name="users")

        with op.batch_alter_table("users", schema=None) as batch_op:
            if _column_exists(inspector, "users", "vpn_uuid"):
                batch_op.drop_column("vpn_uuid")
            if _column_exists(inspector, "users", "oidc_provider"):
                batch_op.drop_column("oidc_provider")
            if _column_exists(inspector, "users", "oidc_id"):
                batch_op.drop_column("oidc_id")
            if _column_exists(inspector, "users", "role"):
                batch_op.drop_column("role")
