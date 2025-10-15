"""
Verify document_uploads table has all required columns
"""
import logging
from sqlalchemy import inspect, text
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    'id': 'integer',
    'filename': 'character varying',
    'original_filename': 'character varying',
    'category': 'character varying',
    'file_type': 'character varying',
    'file_size_bytes': 'integer',
    'status': 'character varying',
    'error_message': 'text',
    'upload_date': 'timestamp with time zone',
    'uploaded_by': 'character varying',
    'chunk_count': 'integer',
    'total_tokens': 'integer',
    'text_preview': 'text',
    'vector_ids': 'json',
    'namespace': 'character varying',
    'processing_started_at': 'timestamp with time zone',
    'processing_completed_at': 'timestamp with time zone',
    'processing_time_ms': 'integer',
    'required_ocr': 'boolean',
    'ocr_confidence': 'double precision',
    'metadata': 'json',
    'is_deleted': 'boolean',
    'deleted_at': 'timestamp with time zone'
}

def verify_schema():
    """Verify all required columns exist"""
    
    inspector = inspect(engine)
    
    # Check if table exists
    if 'document_uploads' not in inspector.get_table_names():
        logger.error("❌ Table 'document_uploads' does not exist!")
        logger.info("Run: python -c \"from config.database import engine, Base; Base.metadata.create_all(bind=engine)\"")
        return False
    
    # Get existing columns
    existing_columns = {
        col['name']: str(col['type']).lower() 
        for col in inspector.get_columns('document_uploads')
    }
    
    logger.info("\n📋 Checking document_uploads schema...")
    
    missing_columns = []
    present_columns = []
    
    for col_name, col_type in REQUIRED_COLUMNS.items():
        if col_name in existing_columns:
            present_columns.append(col_name)
            logger.info(f"  ✅ {col_name}: {existing_columns[col_name]}")
        else:
            missing_columns.append(col_name)
            logger.error(f"  ❌ MISSING: {col_name} ({col_type})")
    
    logger.info(f"\n📊 Summary:")
    logger.info(f"  Present: {len(present_columns)}/{len(REQUIRED_COLUMNS)}")
    logger.info(f"  Missing: {len(missing_columns)}")
    
    if missing_columns:
        logger.error(f"\n⚠️ Missing columns: {', '.join(missing_columns)}")
        logger.info("\n🔧 To fix, run:")
        logger.info("  python add_original_filename_column.py")
        return False
    else:
        logger.info("\n✅ All required columns present!")
        return True

if __name__ == "__main__":
    verify_schema()