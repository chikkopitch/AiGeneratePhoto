"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.type_api import TypeEngine

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _integer_type() -> TypeEngine:
    if op.get_context().dialect.name == "sqlite":
        return sa.Integer()
    return sa.BigInteger()


def _identity() -> tuple[sa.Identity, ...]:
    if op.get_context().dialect.name == "sqlite":
        return ()
    return (sa.Identity(),)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", _integer_type(), *_identity(), nullable=False),
        sa.Column("telegram_id", _integer_type(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )

    op.create_table(
        "generations",
        sa.Column("id", _integer_type(), *_identity(), nullable=False),
        sa.Column("user_id", _integer_type(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generations_status"), "generations", ["status"], unique=False)
    op.create_index(op.f("ix_generations_user_id"), "generations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generations_user_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_status"), table_name="generations")
    op.drop_table("generations")
    op.drop_table("users")
