"""
Complete fix for metadata column issue
1. Renames database column
2. Verifies change
"""
import logging
from sqlalchemy import text, inspect
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_metadata_column():
    """Complete fix for metadata column"""
    
    # Step 1: Rename column in database
    logger.info("Step 1: Renaming database column...")
    
    sql_rename = """
    DO $$ 
    BEGIN 
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='document_uploads' AND column_name='metadata'
        ) THEN
            ALTER TABLE document_uploads RENAME COLUMN metadata TO doc_metadata;
            RAISE NOTICE 'Renamed metadata to doc_metadata';
        ELSIF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='document_uploads' AND column_name='doc_metadata'
        ) THEN
            ALTER TABLE document_uploads ADD COLUMN doc_metadata JSON;
            RAISE NOTICE 'Created doc_metadata column';
        ELSE
            RAISE NOTICE 'doc_metadata column already exists';
        END IF;
    END $$;
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql_rename))
            conn.commit()
        
        logger.info("✅ Database column updated")
        
        # Step 2: Verify
        logger.info("Step 2: Verifying changes...")
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('document_uploads')]
        
        if 'doc_metadata' in columns:
            logger.info("✅ doc_metadata column exists")
        else:
            logger.error("❌ doc_metadata column not found")
            return False
        
        if 'metadata' in columns:
            logger.warning("⚠️ Old 'metadata' column still exists (unexpected)")
        else:
            logger.info("✅ Old 'metadata' column removed")
        
        logger.info("\n✅ Fix completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Restart the server: uvicorn main:app --reload")
        logger.info("2. Test document upload endpoint")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fix failed: {e}")
        return False

if __name__ == "__main__":
    fix_metadata_column()