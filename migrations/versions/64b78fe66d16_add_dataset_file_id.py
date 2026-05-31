"""add dataset file_id

Revision ID: 64b78fe66d16
Revises: 866fd6f95fec
Create Date: 2026-05-30 13:45:38.144427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64b78fe66d16'
down_revision = '866fd6f95fec'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('dataset')]

    # Only add the column if it doesn't already exist (idempotent)
    if 'file_id' not in cols:
        with op.batch_alter_table('dataset', schema=None) as batch_op:
            batch_op.add_column(sa.Column('file_id', sa.String(length=255), nullable=True))
            # leave nullable True for existing rows; app will populate new uploads
            try:
                batch_op.create_unique_constraint('uq_dataset_file_id', 'dataset', ['file_id'])
            except Exception:
                # ignore if constraint cannot be created
                pass


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('dataset')]
    if 'file_id' in cols:
        with op.batch_alter_table('dataset', schema=None) as batch_op:
            try:
                batch_op.drop_constraint('uq_dataset_file_id', 'dataset', type_='unique')
            except Exception:
                pass
            batch_op.drop_column('file_id')
