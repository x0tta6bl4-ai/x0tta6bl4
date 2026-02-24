"""Add sbom_entries, node_binary_attestations, playbook_acks tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-21 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "sbom_entries"):
        op.create_table(
            "sbom_entries",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("version", sa.String(), nullable=False, unique=True),
            sa.Column("format", sa.String(), nullable=True, server_default="CycloneDX-JSON"),
            sa.Column("components_json", sa.Text(), nullable=False),
            sa.Column("checksum_sha256", sa.String(), nullable=False),
            sa.Column("attestation_json", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(inspector, "node_binary_attestations"):
        op.create_table(
            "node_binary_attestations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("node_id", sa.String(), nullable=False, index=True),
            sa.Column("mesh_id", sa.String(), nullable=True, index=True),
            sa.Column("sbom_id", sa.String(), sa.ForeignKey("sbom_entries.id"), nullable=False),
            sa.Column("agent_version", sa.String(), nullable=False),
            sa.Column("checksum_sha256", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="verified"),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(inspector, "playbook_acks"):
        # Only create if signed_playbooks exists (has FK dependency)
        if _table_exists(inspector, "signed_playbooks"):
            op.create_table(
                "playbook_acks",
                sa.Column("id", sa.String(), primary_key=True),
                sa.Column("playbook_id", sa.String(), sa.ForeignKey("signed_playbooks.id"),
                          nullable=False, index=True),
                sa.Column("node_id", sa.String(), nullable=False, index=True),
                sa.Column("status", sa.String(), nullable=False, server_default="completed"),
                sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for t in ("playbook_acks", "node_binary_attestations", "sbom_entries"):
        if _table_exists(inspector, t):
            op.drop_table(t)
