"""remove log channel

Revision ID: f8b9efe0a064
Revises: 16037a723dda
Create Date: 2020-11-19 15:05:32.980537

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8b9efe0a064'
down_revision = '16037a723dda'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('settings', 'log_channel')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('settings', sa.Column('log_channel', sa.BIGINT(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###