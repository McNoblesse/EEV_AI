"""Quick migration script to fix missing columns"""
import logging
from sqlalchemy import text
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_quick_fix():
    """Add missing columns immediately"""
    
    sql_statements = [
        # Add requires_escalation column
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='requires_escalation'
            ) THEN
                ALTER TABLE conversations ADD COLUMN requires_escalation BOOLEAN DEFAULT FALSE;
                RAISE NOTICE 'Added requires_escalation column';
            END IF;
        END $$;
        """,
        
        # Add other critical columns
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='intent_confidence'
            ) THEN
                ALTER TABLE conversations ADD COLUMN intent_confidence FLOAT;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='sub_intent'
            ) THEN
                ALTER TABLE conversations ADD COLUMN sub_intent VARCHAR;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='sentiment_score'
            ) THEN
                ALTER TABLE conversations ADD COLUMN sentiment_score FLOAT DEFAULT 0.0;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='complexity_score'
            ) THEN
                ALTER TABLE conversations ADD COLUMN complexity_score INTEGER;
            END IF;
        END $$;
        """,
        
        # Create conversation_analytics table
        """
        CREATE TABLE IF NOT EXISTS conversation_analytics (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            entities JSONB,
            keywords JSONB,
            complexity_factors JSONB,
            reasoning_steps JSONB,
            tool_calls_used JSONB,
            retrieval_context JSONB,
            processing_time_ms INTEGER,
            tokens_used INTEGER,
            model_used VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT unique_conversation_analytics UNIQUE (conversation_id)
        );
        """,
        
        # Create indexes
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_analytics_conversation_id 
        ON conversation_analytics(conversation_id);
        """,
        
        # Create voice_metadata table
        """
        CREATE TABLE IF NOT EXISTS voice_metadata (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            transcription_model VARCHAR,
            tts_model VARCHAR,
            voice_used VARCHAR,
            audio_file_path VARCHAR,
            audio_duration_seconds FLOAT,
            transcription_confidence FLOAT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT unique_voice_metadata UNIQUE (conversation_id)
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_voice_metadata_conversation_id 
        ON voice_metadata(conversation_id);
        """
    ]
    
    try:
        with engine.connect() as conn:
            for i, sql in enumerate(sql_statements, 1):
                logger.info(f"Executing statement {i}/{len(sql_statements)}...")
                conn.execute(text(sql))
                conn.commit()
        
        logger.info("✅ All migrations completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    run_quick_fix()