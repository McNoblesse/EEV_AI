"""
Quick fix: Add missing original_filename column
"""
import logging
from sqlalchemy import text
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_missing_column():
    """Add original_filename column to document_uploads table"""
    
    sql = """
    DO $$ 
    BEGIN 
        -- Add original_filename if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='document_uploads' AND column_name='original_filename'
        ) THEN
            ALTER TABLE document_uploads 
            ADD COLUMN original_filename VARCHAR NOT NULL DEFAULT '';
            
            -- Update existing records to use filename as original_filename
            UPDATE document_uploads 
            SET original_filename = filename 
            WHERE original_filename = '';
            
            RAISE NOTICE '✅ Added original_filename column';
        ELSE
            RAISE NOTICE '✓ original_filename column already exists';
        END IF;
    END $$;
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    add_missing_column()