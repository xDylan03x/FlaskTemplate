"""Add group permission definitions and unique individual permissions.

Revision ID: 8d3f27c1a609
Revises: 0c4f026cb977
"""
from alembic import op
import sqlalchemy as sa


revision = '8d3f27c1a609'
down_revision = '0c4f026cb977'
branch_labels = None
depends_on = None


def upgrade():
    # Keep the most recently updated definition for each user and key.
    op.execute(sa.text('''
        DELETE FROM user_permission
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, key ORDER BY updated_at DESC, id DESC
                ) AS definition_order
                FROM user_permission
            ) AS ranked_definitions
            WHERE definition_order > 1
        )
    '''))
    with op.batch_alter_table('user_permission') as batch_op:
        batch_op.create_unique_constraint('uq_user_permission_user_key', ['user_id', 'key'])

    op.create_table('user_group_permission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid36', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('value', sa.Boolean(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['user_group.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'key', name='uq_user_group_permission_group_key'),
    )
    op.create_index('ix_user_group_permission_uuid36', 'user_group_permission', ['uuid36'], unique=True)


def downgrade():
    op.drop_index('ix_user_group_permission_uuid36', table_name='user_group_permission')
    op.drop_table('user_group_permission')
    with op.batch_alter_table('user_permission') as batch_op:
        batch_op.drop_constraint('uq_user_permission_user_key', type_='unique')
