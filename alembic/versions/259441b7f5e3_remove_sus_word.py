"""remove sus word

Revision ID: 259441b7f5e3
Revises: f8b9efe0a064
Create Date: 2020-11-22 17:13:40.638086

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '259441b7f5e3'
down_revision = 'f8b9efe0a064'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('sus_words')


def downgrade():
    op.create_table('sus_words',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.BigInteger(), nullable=False),
    sa.Column('regex', sa.Text(), nullable=False),
    sa.Column('auto_delete', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )