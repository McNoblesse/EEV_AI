"""Rename metadata column in document_uploads

Revision ID: 003_rename_metadata
Revises: 002_refactor_schema
Create Date: 2025-01-10 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '003_rename_metadata'
down_revision = '002_refactor_schema'
branch_labels = None
depends_on = None


def upgrade():
    """Rename metadata to doc_metadata"""
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='metadata'
            ) THEN
                ALTER TABLE document_uploads RENAME COLUMN metadata TO doc_metadata;
            END IF;
        END $$;
    """)


def downgrade():
    """Revert doc_metadata to metadata"""
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='doc_metadata'
            ) THEN
                ALTER TABLE document_uploads RENAME COLUMN doc_metadata TO metadata;
            END IF;
        END $$;
    """)