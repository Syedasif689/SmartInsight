"""add dataset download history

Revision ID: c8107e2af3a4
Revises: fb6d88f1738e
Create Date: 2026-05-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c8107e2af3a4'
down_revision = 'fb6d88f1738e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dataset', sa.Column('downloaded_filename', sa.String(length=255), nullable=True))
    op.add_column('dataset', sa.Column('downloaded_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('dataset', 'downloaded_at')
    op.drop_column('dataset', 'downloaded_filename')
