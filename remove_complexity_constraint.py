"""Remove complexity_range check constraint from conversations table"""
import logging
from sqlalchemy import text, inspect
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_constraint():
    """Remove the complexity_range check constraint"""
    
    with engine.connect() as conn:
        try:
            # Check if constraint exists
            result = conn.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'conversations' 
                AND constraint_type = 'CHECK'
                AND constraint_name = 'complexity_range';
            """))
            
            constraint_exists = result.fetchone() is not None
            
            if constraint_exists:
                logger.info("Found complexity_range constraint, removing...")
                
                # Drop the constraint
                conn.execute(text("""
                    ALTER TABLE conversations 
                    DROP CONSTRAINT IF EXISTS complexity_range;
                """))
                conn.commit()
                
                logger.info("✅ Constraint removed successfully!")
            else:
                logger.info("⚠️ No complexity_range constraint found")
            
            # Also check for any other complexity-related constraints
            logger.info("\nChecking for other constraints...")
            result = conn.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_schema = 'public'
                AND constraint_name LIKE '%complexity%';
            """))
            
            constraints = result.fetchall()
            if constraints:
                logger.info("Found complexity-related constraints:")
                for constraint in constraints:
                    logger.info(f"  - {constraint[0]}: {constraint[1]}")
                    
                    # Drop each one
                    conn.execute(text(f"""
                        ALTER TABLE conversations 
                        DROP CONSTRAINT IF EXISTS {constraint[0]};
                    """))
                    conn.commit()
                    logger.info(f"  ✅ Removed: {constraint[0]}")
            else:
                logger.info("No other complexity constraints found")
                
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    remove_constraint()
    print("\n" + "="*60)
    print("✅ All complexity constraints removed!")
    print("You can now insert conversations with any complexity score (0-100)")
    print("="*60)