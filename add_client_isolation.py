"""
Add multi-tenancy support with client isolation
"""
import logging
from sqlalchemy import text
from config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_client_isolation():
    """Add client_id and clients table"""
    
    migrations = [
        # Create clients table with IF NOT EXISTS for indexes
        """
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            client_id VARCHAR UNIQUE NOT NULL,
            client_name VARCHAR NOT NULL,
            api_key VARCHAR UNIQUE NOT NULL,
            api_key_hash VARCHAR NOT NULL,
            namespace_prefix VARCHAR NOT NULL,
            subscription_tier VARCHAR,
            max_documents INTEGER DEFAULT 1000,
            max_storage_mb INTEGER DEFAULT 10000,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            contact_email VARCHAR,
            company_domain VARCHAR,
            client_metadata JSON
        );
        
        -- ✅ CREATE INDEX IF NOT EXISTS (safe)
        CREATE INDEX IF NOT EXISTS ix_clients_client_id ON clients(client_id);
        CREATE INDEX IF NOT EXISTS ix_clients_is_active ON clients(is_active);
        """,
        
        # Add client_id to document_uploads
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='document_uploads' AND column_name='client_id'
            ) THEN
                ALTER TABLE document_uploads ADD COLUMN client_id VARCHAR;
                ALTER TABLE document_uploads ADD COLUMN client_name VARCHAR;
                
                -- Set default client for existing documents
                UPDATE document_uploads 
                SET client_id = 'default_client', 
                    client_name = 'Default Client'
                WHERE client_id IS NULL;
                
                ALTER TABLE document_uploads ALTER COLUMN client_id SET NOT NULL;
                
                -- ✅ CREATE INDEX IF NOT EXISTS
                CREATE INDEX IF NOT EXISTS ix_document_uploads_client_id ON document_uploads(client_id);
                
                RAISE NOTICE '✅ Added client_id to document_uploads';
            END IF;
        END $$;
        """,
        
        # Add client_id to conversations
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='conversations' AND column_name='client_id'
            ) THEN
                ALTER TABLE conversations ADD COLUMN client_id VARCHAR;
                
                -- Set default for existing conversations
                UPDATE conversations 
                SET client_id = 'default_client'
                WHERE client_id IS NULL;
                
                -- ✅ CREATE INDEX IF NOT EXISTS
                CREATE INDEX IF NOT EXISTS ix_conversations_client_id ON conversations(client_id);
                
                RAISE NOTICE '✅ Added client_id to conversations';
            END IF;
        END $$;
        """,
        
        # Insert default client
        """
        INSERT INTO clients (
            client_id, client_name, api_key, api_key_hash, 
            namespace_prefix, subscription_tier, is_active
        ) VALUES (
            'default_client',
            'Default Client',
            '6fcbc285706bdf4fdae56f252653036b816651a6c63e057959d9b90a71a779757760436324534136ed1ad42915f2a099eb4f31dd030d661ce5a86b5487ffe480',
            'hashed_key_placeholder',
            'client_default',
            'enterprise',
            TRUE
        )
        ON CONFLICT (client_id) DO NOTHING;
        """
    ]
    
    try:
        with engine.connect() as conn:
            for i, migration in enumerate(migrations, 1):
                logger.info(f"Running migration {i}/{len(migrations)}...")
                conn.execute(text(migration))
                conn.commit()
        
        logger.info("✅ Client isolation migration completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    add_client_isolation()