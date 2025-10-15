"""Add all missing columns to conversations table"""
import logging
from sqlalchemy import text, inspect
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_missing_columns():
    """Add all missing columns that are used in the codebase"""
    
    # Get current columns
    inspector = inspect(engine)
    existing_columns = [c['name'] for c in inspector.get_columns('conversations')]
    logger.info(f"Current columns: {existing_columns}")
    
    # Define all required columns with their SQL types
    required_columns = {
        'requires_escalation': 'BOOLEAN DEFAULT FALSE',
        'intent_confidence': 'FLOAT',
        'sub_intent': 'VARCHAR',
        'sentiment_score': 'FLOAT DEFAULT 0.0',
        'complexity_score': 'INTEGER',
        'entities': 'JSONB',
        'keywords': 'JSONB',
        'complexity_factors': 'JSONB',
        'reasoning_steps': 'JSONB',
        'tool_calls_used': 'JSONB',
        'retrieval_context': 'JSONB',
        'processing_time_ms': 'INTEGER',
        'tokens_used': 'INTEGER',
        'model_used': 'VARCHAR',
        'user_type': 'VARCHAR',
        'conversation_summary': 'TEXT',
        'conversation_ended': 'BOOLEAN DEFAULT FALSE',
        'transcription_model': 'VARCHAR',
        'tts_model': 'VARCHAR',
        'voice_used': 'VARCHAR',
        'audio_file_path': 'VARCHAR',
        'audio_duration_seconds': 'FLOAT',
        'transcription_confidence': 'FLOAT',
    }
    
    # Add missing columns
    with engine.connect() as conn:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                try:
                    sql = f"""
                    ALTER TABLE conversations 
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type};
                    """
                    logger.info(f"Adding column: {column_name} ({column_type})")
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"✅ Added: {column_name}")
                except Exception as e:
                    logger.error(f"❌ Failed to add {column_name}: {e}")
                    conn.rollback()
            else:
                logger.info(f"⏭️  Column already exists: {column_name}")
    
    # Now create the analytics tables
    logger.info("\n" + "=" * 60)
    logger.info("Creating analytics tables...")
    logger.info("=" * 60)
    
    create_tables_sql = [
        # conversation_analytics table
        """
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
            
            CONSTRAINT unique_conversation_analytics UNIQUE (conversation_id)
        );
        """,
        
        # Index for conversation_analytics
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_analytics_conversation_id 
        ON conversation_analytics(conversation_id);
        """,
        
        # voice_metadata table
        """
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
            
            CONSTRAINT unique_voice_metadata UNIQUE (conversation_id)
        );
        """,
        
        # Index for voice_metadata
        """
        CREATE INDEX IF NOT EXISTS idx_voice_metadata_conversation_id 
        ON voice_metadata(conversation_id);
        """
    ]
    
    with engine.connect() as conn:
        for sql in create_tables_sql:
            try:
                logger.info("Executing table creation...")
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                logger.error(f"Error creating table: {e}")
                conn.rollback()
    
    logger.info("\n✅ All migrations completed!")
    logger.info("=" * 60)
    
    # Verify
    logger.info("\nVerifying changes...")
    inspector = inspect(engine)
    final_columns = [c['name'] for c in inspector.get_columns('conversations')]
    logger.info(f"Final column count: {len(final_columns)}")
    
    missing = set(required_columns.keys()) - set(final_columns)
    if missing:
        logger.warning(f"Still missing: {missing}")
    else:
        logger.info("✅ All required columns present!")
    
    # Check new tables
    tables = inspector.get_table_names()
    logger.info(f"\nAll tables: {tables}")
    logger.info(f"Has conversation_analytics? {'conversation_analytics' in tables}")
    logger.info(f"Has voice_metadata? {'voice_metadata' in tables}")

if __name__ == "__main__":
    add_missing_columns()