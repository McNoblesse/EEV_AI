"""Add document_uploads table for knowledge base

Revision ID: 001_document_uploads
Revises: 
Create Date: 2025-01-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_document_uploads'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create document_uploads table"""
    op.create_table(
        'document_uploads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('upload_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('uploaded_by', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('text_preview', sa.Text(), nullable=True),
        sa.Column('vector_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('namespace', sa.String(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('required_ocr', sa.Boolean(), nullable=True),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_document_uploads_id'), 'document_uploads', ['id'], unique=False)
    op.create_index(op.f('ix_document_uploads_filename'), 'document_uploads', ['filename'], unique=False)
    op.create_index(op.f('ix_document_uploads_category'), 'document_uploads', ['category'], unique=False)
    op.create_index(op.f('ix_document_uploads_upload_date'), 'document_uploads', ['upload_date'], unique=False)
    op.create_index(op.f('ix_document_uploads_status'), 'document_uploads', ['status'], unique=False)
    op.create_index(op.f('ix_document_uploads_is_deleted'), 'document_uploads', ['is_deleted'], unique=False)


def downgrade():
    """Drop document_uploads table"""
    op.drop_index(op.f('ix_document_uploads_is_deleted'), table_name='document_uploads')
    op.drop_index(op.f('ix_document_uploads_status'), table_name='document_uploads')
    op.drop_index(op.f('ix_document_uploads_upload_date'), table_name='document_uploads')
    op.drop_index(op.f('ix_document_uploads_category'), table_name='document_uploads')
    op.drop_index(op.f('ix_document_uploads_filename'), table_name='document_uploads')
    op.drop_index(op.f('ix_document_uploads_id'), table_name='document_uploads')
    op.drop_table('document_uploads')
