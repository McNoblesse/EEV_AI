import logging
from sqlalchemy import text
from config.database import engine

logger = logging.getLogger(__name__)

def run_migrations():
    """
    Safe database migrations that won't break existing data
    Adds new columns to existing tables and updates enums
    """
    migrations = [
        # Update enums to include all current values
        """
        DO $$ 
        BEGIN 
            -- Add missing values to intentenum
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'intentenum') AND enumlabel = 'general_question') THEN
                ALTER TYPE intentenum ADD VALUE 'general_question';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'intentenum') AND enumlabel = 'follow_up') THEN
                ALTER TYPE intentenum ADD VALUE 'follow_up';
            END IF;
            
            -- Add missing values to sentimentenum (if any)
            -- Assuming all values are present; add checks if needed
            
            -- Add missing values to complexityenum (if any)
            -- Assuming all values are present; add checks if needed
            
            -- Add missing values to channelenum (if any)
            -- Assuming all values are present; add checks if needed
            
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'Enum update error: %', SQLERRM;
        END $$;
        """,
        
        # Conversation table migrations - Add all missing columns
        """
        DO $$ 
        BEGIN 
            -- Add new columns if they don't exist
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='intent_confidence') THEN
                ALTER TABLE conversations ADD COLUMN intent_confidence FLOAT;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='sub_intent') THEN
                ALTER TABLE conversations ADD COLUMN sub_intent VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='sentiment_score') THEN
                ALTER TABLE conversations ADD COLUMN sentiment_score FLOAT;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='complexity') THEN
                ALTER TABLE conversations ADD COLUMN complexity VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='complexity_factors') THEN
                ALTER TABLE conversations ADD COLUMN complexity_factors JSON;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='entities') THEN
                ALTER TABLE conversations ADD COLUMN entities JSON;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='keywords') THEN
                ALTER TABLE conversations ADD COLUMN keywords JSON;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='user_type') THEN
                ALTER TABLE conversations ADD COLUMN user_type VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='transcription_model') THEN
                ALTER TABLE conversations ADD COLUMN transcription_model VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='tts_model') THEN
                ALTER TABLE conversations ADD COLUMN tts_model VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='voice_used') THEN
                ALTER TABLE conversations ADD COLUMN voice_used VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='audio_file_path') THEN
                ALTER TABLE conversations ADD COLUMN audio_file_path VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='requires_knowledge_base') THEN
                ALTER TABLE conversations ADD COLUMN requires_knowledge_base BOOLEAN DEFAULT FALSE;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='requires_human_escalation') THEN
                ALTER TABLE conversations ADD COLUMN requires_human_escalation BOOLEAN DEFAULT FALSE;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='can_respond_directly') THEN
                ALTER TABLE conversations ADD COLUMN can_respond_directly BOOLEAN DEFAULT FALSE;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='conversation_summary') THEN
                ALTER TABLE conversations ADD COLUMN conversation_summary TEXT;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='conversation_ended') THEN
                ALTER TABLE conversations ADD COLUMN conversation_ended BOOLEAN DEFAULT FALSE;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='end_reason') THEN
                ALTER TABLE conversations ADD COLUMN end_reason VARCHAR;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='follow_up_required') THEN
                ALTER TABLE conversations ADD COLUMN follow_up_required BOOLEAN DEFAULT FALSE;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='follow_up_details') THEN
                ALTER TABLE conversations ADD COLUMN follow_up_details TEXT;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='reasoning_steps') THEN
                ALTER TABLE conversations ADD COLUMN reasoning_steps JSON;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='tool_calls_used') THEN
                ALTER TABLE conversations ADD COLUMN tool_calls_used JSON;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='retrieval_context') THEN
                ALTER TABLE conversations ADD COLUMN retrieval_context JSON;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='processing_time_ms') THEN
                ALTER TABLE conversations ADD COLUMN processing_time_ms INTEGER;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='tokens_used') THEN
                ALTER TABLE conversations ADD COLUMN tokens_used INTEGER;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='conversations' AND column_name='model_used') THEN
                ALTER TABLE conversations ADD COLUMN model_used VARCHAR;
            END IF;
            
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'Migration error: %', SQLERRM;
        END $$;
        """,
        
        # Create new tables if they don't exist - Complete definitions
        """
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR UNIQUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP WITH TIME ZONE,
            channel VARCHAR NOT NULL,
            user_id VARCHAR,
            device_info JSON,
            current_intent VARCHAR,
            current_complexity VARCHAR,
            conversation_turn_count INTEGER DEFAULT 0,
            total_tokens_used INTEGER DEFAULT 0,
            average_response_time FLOAT,
            escalation_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            requires_follow_up BOOLEAN DEFAULT FALSE,
            satisfaction_score INTEGER,
            langgraph_thread_id VARCHAR,
            checkpoint_data JSON
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS knowledge_base_usage (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            query_text TEXT NOT NULL,
            search_terms JSON,
            results_count INTEGER,
            retrieval_success BOOLEAN DEFAULT TRUE,
            response_relevance INTEGER,
            tools_used JSON,
            retrieval_time_ms INTEGER,
            source_documents JSON
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS escalation_logs (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            ticket_id INTEGER,
            escalation_reason TEXT NOT NULL,
            original_query TEXT NOT NULL,
            analysis_summary JSON,
            assigned_agent VARCHAR,
            resolution_time TIMESTAMP WITH TIME ZONE,
            resolution_notes TEXT,
            status VARCHAR DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            customer_satisfaction INTEGER,
            agent_feedback TEXT
        );
        """
    ]
    
    try:
        with engine.connect() as conn:
            for migration in migrations:
                conn.execute(text(migration))
            conn.commit()
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migrations()