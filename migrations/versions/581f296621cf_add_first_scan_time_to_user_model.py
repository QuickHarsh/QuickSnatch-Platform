"""Add first_scan_time to User model

Revision ID: 581f296621cf
Revises: 
Create Date: 2025-04-02 23:19:58.866686

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '581f296621cf'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('level_time', schema=None) as batch_op:
        batch_op.alter_column('time_spent',
               existing_type=sa.INTEGER(),
               type_=sa.Interval(),
               existing_nullable=True)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('first_scan_time', sa.DateTime(), nullable=True))
        batch_op.drop_column('last_completed_level')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_completed_level', sa.INTEGER(), nullable=True))
        batch_op.drop_column('first_scan_time')

    with op.batch_alter_table('level_time', schema=None) as batch_op:
        batch_op.alter_column('time_spent',
               existing_type=sa.Interval(),
               type_=sa.INTEGER(),
               existing_nullable=True)

    # ### end Alembic commands ###
