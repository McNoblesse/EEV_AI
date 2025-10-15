"""Split conversation table into focused schemas

Revision ID: 002_split_conversation_tables
Revises: 001_document_uploads
Create Date: 2025-01-10 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_split_conversation_tables'
down_revision = '001_document_uploads'
branch_labels = None
depends_on = None


def upgrade():
    """
    Split conversations table into 3 focused tables:
    1. conversations (core data only)
    2. conversation_analytics (debug/analysis data)
    3. voice_metadata (voice-specific fields)
    """
    
    # 1. Create conversation_analytics table
    op.create_table(
        'conversation_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('entities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('complexity_factors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reasoning_steps', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_calls_used', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('retrieval_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_conversation_analytics_conversation_id'), 'conversation_analytics', ['conversation_id'], unique=False)
    
    # 2. Create voice_metadata table
    op.create_table(
        'voice_metadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('transcription_model', sa.String(), nullable=True),
        sa.Column('tts_model', sa.String(), nullable=True),
        sa.Column('voice_used', sa.String(), nullable=True),
        sa.Column('audio_file_path', sa.String(), nullable=True),
        sa.Column('audio_duration_seconds', sa.Float(), nullable=True),
        sa.Column('transcription_confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_voice_metadata_conversation_id'), 'voice_metadata', ['conversation_id'], unique=False)
    
    # 3. Migrate existing data (only if conversations table exists with data)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'conversations' in inspector.get_table_names():
        # Get existing columns
        existing_columns = {col['name'] for col in inspector.get_columns('conversations')}
        
        # Migrate to conversation_analytics (only if columns exist)
        analytics_cols = ['entities', 'keywords', 'complexity_factors', 'reasoning_steps',
                         'tool_calls_used', 'retrieval_context', 'processing_time_ms',
                         'tokens_used', 'model_used']
        
        existing_analytics_cols = [col for col in analytics_cols if col in existing_columns]
        
        if existing_analytics_cols:
            select_stmt = ', '.join(existing_analytics_cols)
            op.execute(f"""
                INSERT INTO conversation_analytics (conversation_id, {select_stmt})
                SELECT id, {select_stmt}
                FROM conversations
                WHERE entities IS NOT NULL OR reasoning_steps IS NOT NULL;
            """)
            print(f"✅ Migrated {len(existing_analytics_cols)} analytics columns")
        
        # Migrate to voice_metadata (only if columns exist)
        voice_cols = ['transcription_model', 'tts_model', 'voice_used', 'audio_file_path']
        existing_voice_cols = [col for col in voice_cols if col in existing_columns]
        
        if existing_voice_cols:
            select_stmt_voice = ', '.join(existing_voice_cols)
            op.execute(f"""
                INSERT INTO voice_metadata (conversation_id, {select_stmt_voice})
                SELECT id, {select_stmt_voice}
                FROM conversations
                WHERE transcription_model IS NOT NULL;
            """)
            print(f"✅ Migrated {len(existing_voice_cols)} voice columns")
        
        # 4. Drop migrated columns from conversations table
        all_columns_to_drop = analytics_cols + voice_cols + [
            'sub_intent', 'sentiment_score', 'complexity', 'user_type',
            'requires_knowledge_base', 'requires_human_escalation',
            'can_respond_directly', 'conversation_summary', 'conversation_ended',
            'end_reason', 'follow_up_required', 'follow_up_details'
        ]
        
        for col in all_columns_to_drop:
            if col in existing_columns:
                try:
                    op.drop_column('conversations', col)
                    print(f"✅ Dropped: {col}")
                except Exception as e:
                    print(f"⚠️  Could not drop {col}: {e}")
    else:
        print("ℹ️  Conversations table doesn't exist yet, skipping migration")
    
    print("✅ Database schema refactored successfully")


def downgrade():
    """Reverse the split (restore original schema)"""
    
    # Add columns back to conversations
    op.add_column('conversations', sa.Column('entities', postgresql.JSONB(), nullable=True))
    op.add_column('conversations', sa.Column('keywords', postgresql.JSONB(), nullable=True))
    # ... (add all dropped columns)
    
    # Migrate data back
    op.execute("""
        UPDATE conversations c
        SET entities = ca.entities,
            keywords = ca.keywords,
            reasoning_steps = ca.reasoning_steps
        FROM conversation_analytics ca
        WHERE c.id = ca.conversation_id;
    """)
    
    # Drop new tables
    op.drop_table('voice_metadata')
    op.drop_table('conversation_analytics')