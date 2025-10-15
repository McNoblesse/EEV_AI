"""
Complete migration to add all missing columns to document_uploads
"""
import logging
from sqlalchemy import text
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_complete_migration():
    """Add all missing columns with proper defaults"""
    
    migrations = [
        # Add original_filename
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='original_filename'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN original_filename VARCHAR;
                UPDATE document_uploads SET original_filename = filename WHERE original_filename IS NULL;
                ALTER TABLE document_uploads ALTER COLUMN original_filename SET NOT NULL;
            END IF;
        END $$;
        """,
        
        # Add file_size_bytes if missing
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='file_size_bytes'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN file_size_bytes INTEGER DEFAULT 0;
            END IF;
        END $$;
        """,
        
        # Add uploaded_by if missing
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='uploaded_by'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN uploaded_by VARCHAR;
            END IF;
        END $$;
        """,
        
        # Add error_message if missing
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='error_message'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN error_message TEXT;
            END IF;
        END $$;
        """,
        
        # Add processing columns
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='total_tokens'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN total_tokens INTEGER;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='text_preview'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN text_preview TEXT;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='vector_ids'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN vector_ids JSON;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='namespace'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN namespace VARCHAR;
            END IF;
        END $$;
        """,
        
        # Add timing columns
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='processing_started_at'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN processing_started_at TIMESTAMP WITH TIME ZONE;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='processing_completed_at'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN processing_completed_at TIMESTAMP WITH TIME ZONE;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='processing_time_ms'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN processing_time_ms INTEGER;
            END IF;
        END $$;
        """,
        
        # Add OCR columns
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='required_ocr'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN required_ocr BOOLEAN;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='ocr_confidence'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN ocr_confidence FLOAT;
            END IF;
        END $$;
        """,
        
        # Add metadata column
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='metadata'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN metadata JSON;
            END IF;
        END $$;
        """
    ]
    
    try:
        with engine.connect() as conn:
            for i, migration in enumerate(migrations, 1):
                logger.info(f"Running migration {i}/{len(migrations)}...")
                conn.execute(text(migration))
                conn.commit()
        
        logger.info("✅ All migrations completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    run_complete_migration()