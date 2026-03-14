"""Baseline Eurydice schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app import models as _shared_models  # noqa: F401
from app.domains.base import DEFAULT_DOMAIN
from app.domains.music import models as _music_models  # noqa: F401
from app.models import Base


revision = "20260314_0001"
down_revision = None
branch_labels = None
depends_on = None


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    default_domain_literal = _sql_string_literal(DEFAULT_DOMAIN)
    op.execute(
        sa.text(
            "ALTER TABLE sessions "
            f"ADD COLUMN IF NOT EXISTS domain VARCHAR(16) NOT NULL DEFAULT {default_domain_literal}"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE sessions ALTER COLUMN domain SET DEFAULT {default_domain_literal}")
    )
    op.execute(sa.text("ALTER TABLE music_live_tool_calls ADD COLUMN IF NOT EXISTS error_kind VARCHAR(24)"))


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
