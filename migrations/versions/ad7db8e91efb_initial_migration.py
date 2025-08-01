"""Initial migration

Revision ID: ad7db8e91efb
Revises: 
Create Date: 2025-07-16 08:50:56.277388

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'ad7db8e91efb'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('contributor_info',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('dictionaries',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('discussion_boards',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('genres',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('proof_page_statuses',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('roles',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('site_project_sponsorship',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('sa_title', sa.String(), nullable=False),
    sa.Column('en_title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('cost_inr', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('texts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('header', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('is_banned', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('auth_password_reset_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_auth_password_reset_tokens_user_id'), 'auth_password_reset_tokens', ['user_id'], unique=False)
    op.create_table('blog_posts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_blog_posts_author_id'), 'blog_posts', ['author_id'], unique=False)
    op.create_table('dictionary_entries',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dictionary_id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['dictionary_id'], ['dictionaries.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dictionary_entries_dictionary_id'), 'dictionary_entries', ['dictionary_id'], unique=False)
    op.create_index(op.f('ix_dictionary_entries_key'), 'dictionary_entries', ['key'], unique=False)
    op.create_table('discussion_threads',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['board_id'], ['discussion_boards.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_discussion_threads_author_id'), 'discussion_threads', ['author_id'], unique=False)
    op.create_index(op.f('ix_discussion_threads_board_id'), 'discussion_threads', ['board_id'], unique=False)
    op.create_table('proof_projects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('display_title', sa.String(), nullable=False),
    sa.Column('print_title', sa.String(), nullable=False),
    sa.Column('author', sa.String(), nullable=False),
    sa.Column('editor', sa.String(), nullable=False),
    sa.Column('publisher', sa.String(), nullable=False),
    sa.Column('publication_year', sa.String(), nullable=False),
    sa.Column('worldcat_link', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('page_numbers', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('creator_id', sa.Integer(), nullable=True),
    sa.Column('genre_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['board_id'], ['discussion_boards.id'], ),
    sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['genre_id'], ['genres.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_proof_projects_board_id'), 'proof_projects', ['board_id'], unique=False)
    op.create_index(op.f('ix_proof_projects_creator_id'), 'proof_projects', ['creator_id'], unique=False)
    op.create_index(op.f('ix_proof_projects_genre_id'), 'proof_projects', ['genre_id'], unique=False)
    op.create_table('text_sections',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('text_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['text_id'], ['texts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_text_sections_slug'), 'text_sections', ['slug'], unique=False)
    op.create_index(op.f('ix_text_sections_text_id'), 'text_sections', ['text_id'], unique=False)
    op.create_table('user_roles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    op.create_index(op.f('ix_user_roles_role_id'), 'user_roles', ['role_id'], unique=False)
    op.create_index(op.f('ix_user_roles_user_id'), 'user_roles', ['user_id'], unique=False)
    op.create_table('discussion_posts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('thread_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['board_id'], ['discussion_boards.id'], ),
    sa.ForeignKeyConstraint(['thread_id'], ['discussion_threads.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_discussion_posts_author_id'), 'discussion_posts', ['author_id'], unique=False)
    op.create_index(op.f('ix_discussion_posts_board_id'), 'discussion_posts', ['board_id'], unique=False)
    op.create_index(op.f('ix_discussion_posts_thread_id'), 'discussion_posts', ['thread_id'], unique=False)
    op.create_table('proof_pages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('ocr_bounding_boxes', sa.Text(), nullable=True),
    sa.Column('status_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['proof_projects.id'], ),
    sa.ForeignKeyConstraint(['status_id'], ['proof_page_statuses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proof_pages_project_id'), 'proof_pages', ['project_id'], unique=False)
    op.create_index(op.f('ix_proof_pages_slug'), 'proof_pages', ['slug'], unique=False)
    op.create_index(op.f('ix_proof_pages_status_id'), 'proof_pages', ['status_id'], unique=False)
    op.create_table('text_blocks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('text_id', sa.Integer(), nullable=False),
    sa.Column('section_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('xml', sa.Text(), nullable=False),
    sa.Column('n', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['text_sections.id'], ),
    sa.ForeignKeyConstraint(['text_id'], ['texts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_text_blocks_section_id'), 'text_blocks', ['section_id'], unique=False)
    op.create_index(op.f('ix_text_blocks_slug'), 'text_blocks', ['slug'], unique=False)
    op.create_index(op.f('ix_text_blocks_text_id'), 'text_blocks', ['text_id'], unique=False)
    op.create_table('block_parses',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('text_id', sa.Integer(), nullable=False),
    sa.Column('block_id', sa.Integer(), nullable=False),
    sa.Column('data', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['block_id'], ['text_blocks.id'], ),
    sa.ForeignKeyConstraint(['text_id'], ['texts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_block_parses_block_id'), 'block_parses', ['block_id'], unique=False)
    op.create_index(op.f('ix_block_parses_text_id'), 'block_parses', ['text_id'], unique=False)
    op.create_table('proof_revisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('page_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('status_id', sa.Integer(), nullable=False),
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['page_id'], ['proof_pages.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['proof_projects.id'], ),
    sa.ForeignKeyConstraint(['status_id'], ['proof_page_statuses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proof_revisions_author_id'), 'proof_revisions', ['author_id'], unique=False)
    op.create_index(op.f('ix_proof_revisions_page_id'), 'proof_revisions', ['page_id'], unique=False)
    op.create_index(op.f('ix_proof_revisions_project_id'), 'proof_revisions', ['project_id'], unique=False)
    op.create_index(op.f('ix_proof_revisions_status_id'), 'proof_revisions', ['status_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_proof_revisions_status_id'), table_name='proof_revisions')
    op.drop_index(op.f('ix_proof_revisions_project_id'), table_name='proof_revisions')
    op.drop_index(op.f('ix_proof_revisions_page_id'), table_name='proof_revisions')
    op.drop_index(op.f('ix_proof_revisions_author_id'), table_name='proof_revisions')
    op.drop_table('proof_revisions')
    op.drop_index(op.f('ix_block_parses_text_id'), table_name='block_parses')
    op.drop_index(op.f('ix_block_parses_block_id'), table_name='block_parses')
    op.drop_table('block_parses')
    op.drop_index(op.f('ix_text_blocks_text_id'), table_name='text_blocks')
    op.drop_index(op.f('ix_text_blocks_slug'), table_name='text_blocks')
    op.drop_index(op.f('ix_text_blocks_section_id'), table_name='text_blocks')
    op.drop_table('text_blocks')
    op.drop_index(op.f('ix_proof_pages_status_id'), table_name='proof_pages')
    op.drop_index(op.f('ix_proof_pages_slug'), table_name='proof_pages')
    op.drop_index(op.f('ix_proof_pages_project_id'), table_name='proof_pages')
    op.drop_table('proof_pages')
    op.drop_index(op.f('ix_discussion_posts_thread_id'), table_name='discussion_posts')
    op.drop_index(op.f('ix_discussion_posts_board_id'), table_name='discussion_posts')
    op.drop_index(op.f('ix_discussion_posts_author_id'), table_name='discussion_posts')
    op.drop_table('discussion_posts')
    op.drop_index(op.f('ix_user_roles_user_id'), table_name='user_roles')
    op.drop_index(op.f('ix_user_roles_role_id'), table_name='user_roles')
    op.drop_table('user_roles')
    op.drop_index(op.f('ix_text_sections_text_id'), table_name='text_sections')
    op.drop_index(op.f('ix_text_sections_slug'), table_name='text_sections')
    op.drop_table('text_sections')
    op.drop_index(op.f('ix_proof_projects_genre_id'), table_name='proof_projects')
    op.drop_index(op.f('ix_proof_projects_creator_id'), table_name='proof_projects')
    op.drop_index(op.f('ix_proof_projects_board_id'), table_name='proof_projects')
    op.drop_table('proof_projects')
    op.drop_index(op.f('ix_discussion_threads_board_id'), table_name='discussion_threads')
    op.drop_index(op.f('ix_discussion_threads_author_id'), table_name='discussion_threads')
    op.drop_table('discussion_threads')
    op.drop_index(op.f('ix_dictionary_entries_key'), table_name='dictionary_entries')
    op.drop_index(op.f('ix_dictionary_entries_dictionary_id'), table_name='dictionary_entries')
    op.drop_table('dictionary_entries')
    op.drop_index(op.f('ix_blog_posts_author_id'), table_name='blog_posts')
    op.drop_table('blog_posts')
    op.drop_index(op.f('ix_auth_password_reset_tokens_user_id'), table_name='auth_password_reset_tokens')
    op.drop_table('auth_password_reset_tokens')
    op.drop_table('users')
    op.drop_table('texts')
    op.drop_table('site_project_sponsorship')
    op.drop_table('roles')
    op.drop_table('proof_page_statuses')
    op.drop_table('genres')
    op.drop_table('discussion_boards')
    op.drop_table('dictionaries')
    op.drop_table('contributor_info')
    # ### end Alembic commands ###
