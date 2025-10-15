# alembic/versions/002_refactor_conversation_schema.py
"""Refactor conversation schema - split into focused tables

Revision ID: 002_refactor_schema
Revises: 001_initial
Create Date: 2025-01-10 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_refactor_schema'
down_revision = None  # Set to your latest revision ID
branch_labels = None
depends_on = None


def upgrade():
    """
    Phase 1: Add missing columns to conversations table
    Phase 2: Create new analytics and voice_metadata tables
    Phase 3: Migrate data
    """
    
    # =============================================
    # PHASE 1: Add Missing Columns to Conversations
    # =============================================
    
    # Check and add requires_escalation column
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='requires_escalation'
            ) THEN
                ALTER TABLE conversations ADD COLUMN requires_escalation BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
    """)
    
    # Add other missing core columns
    op.execute("""
        DO $$ 
        BEGIN 
            -- Add intent_confidence if missing
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='intent_confidence'
            ) THEN
                ALTER TABLE conversations ADD COLUMN intent_confidence FLOAT;
            END IF;
            
            -- Add sub_intent if missing
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='sub_intent'
            ) THEN
                ALTER TABLE conversations ADD COLUMN sub_intent VARCHAR;
            END IF;
            
            -- Add sentiment_score if missing
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='sentiment_score'
            ) THEN
                ALTER TABLE conversations ADD COLUMN sentiment_score FLOAT;
            END IF;
            
            -- Add complexity_score if missing
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='complexity_score'
            ) THEN
                ALTER TABLE conversations ADD COLUMN complexity_score INTEGER;
            END IF;
            
        END $$;
    """)
    
    # =============================================
    # PHASE 2: Create New Tables
    # =============================================
    
    # Create conversation_analytics table
    op.execute("""
        CREATE TABLE IF NOT EXISTS conversation_analytics (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            
            -- Extracted data
            entities JSONB,
            keywords JSONB,
            complexity_factors JSONB,
            
            -- Reasoning trace
            reasoning_steps JSONB,
            tool_calls_used JSONB,
            retrieval_context JSONB,
            
            -- Performance metrics
            processing_time_ms INTEGER,
            tokens_used INTEGER,
            model_used VARCHAR,
            
            -- Timestamp
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            -- Index for fast lookups
            CONSTRAINT unique_conversation_analytics UNIQUE (conversation_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_conversation_analytics_conversation_id 
        ON conversation_analytics(conversation_id);
    """)
    
    # Create voice_metadata table
    op.execute("""
        CREATE TABLE IF NOT EXISTS voice_metadata (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            
            -- Voice-specific fields
            transcription_model VARCHAR,
            tts_model VARCHAR,
            voice_used VARCHAR,
            audio_file_path VARCHAR,
            audio_duration_seconds FLOAT,
            transcription_confidence FLOAT,
            
            -- Timestamp
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            -- Index for fast lookups
            CONSTRAINT unique_voice_metadata UNIQUE (conversation_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_voice_metadata_conversation_id 
        ON voice_metadata(conversation_id);
    """)
    
    # =============================================
    # PHASE 3: Migrate Existing Data (if columns exist)
    # =============================================
    
    # Migrate analytics data if columns exist
    op.execute("""
        DO $$ 
        BEGIN 
            -- Check if old analytics columns exist before migration
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='entities'
            ) THEN
                -- Migrate existing analytics data
                INSERT INTO conversation_analytics (
                    conversation_id, entities, keywords, complexity_factors,
                    reasoning_steps, tool_calls_used, retrieval_context,
                    processing_time_ms, tokens_used, model_used
                )
                SELECT 
                    id, 
                    entities, 
                    keywords, 
                    complexity_factors,
                    reasoning_steps, 
                    tool_calls_used, 
                    retrieval_context,
                    processing_time_ms, 
                    tokens_used, 
                    model_used
                FROM conversations
                WHERE entities IS NOT NULL 
                   OR reasoning_steps IS NOT NULL
                   OR processing_time_ms IS NOT NULL
                ON CONFLICT (conversation_id) DO NOTHING;
            END IF;
        END $$;
    """)
    
    # Migrate voice metadata if columns exist
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='transcription_model'
            ) THEN
                INSERT INTO voice_metadata (
                    conversation_id, transcription_model, tts_model, 
                    voice_used, audio_file_path
                )
                SELECT 
                    id, 
                    transcription_model, 
                    tts_model, 
                    voice_used, 
                    audio_file_path
                FROM conversations
                WHERE transcription_model IS NOT NULL
                   OR tts_model IS NOT NULL
                   OR voice_used IS NOT NULL
                ON CONFLICT (conversation_id) DO NOTHING;
            END IF;
        END $$;
    """)
    
    print("✅ Migration completed: Core columns added, analytics tables created")


def downgrade():
    """Reverse the migration"""
    
    # Drop new tables
    op.execute("DROP TABLE IF EXISTS voice_metadata CASCADE;")
    op.execute("DROP TABLE IF EXISTS conversation_analytics CASCADE;")
    
    # Remove added columns (optional - be careful with data loss)
    op.execute("""
        DO $$ 
        BEGIN 
            -- Only drop if you want to fully reverse
            -- ALTER TABLE conversations DROP COLUMN IF EXISTS requires_escalation;
            -- ALTER TABLE conversations DROP COLUMN IF EXISTS intent_confidence;
            -- ALTER TABLE conversations DROP COLUMN IF EXISTS sub_intent;
            NULL;
        END $$;
    """)
    
    print("⚠️ Migration reversed")