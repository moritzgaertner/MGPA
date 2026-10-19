"""enable pgvector extension

Revision ID: 61179f00c50a
Revises:
Create Date: 2026-10-19 19:33:07.029321

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61179f00c50a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pgvector so tables can use the `vector` column type."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove pgvector again (only possible once no table uses it)."""
    op.execute("DROP EXTENSION IF EXISTS vector")
