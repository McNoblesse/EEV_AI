"""
Client onboarding script
Creates new client with unique API key and namespace
"""

import sys
import os

# ✅ ADD: Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import secrets
import hashlib
from sqlalchemy.orm import Session
from config.database import SessionLocal
from model.database_models import Client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_api_key() -> str:
    """Generate secure 128-character API key"""
    return secrets.token_hex(64)

def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def create_client(
    client_name: str,
    contact_email: str,
    company_domain: str = None,
    subscription_tier: str = "basic",
    max_documents: int = 1000,
    max_storage_mb: int = 10000
) -> dict:
    """
    Create new client with isolated knowledge base
    
    Args:
        client_name: Company name
        contact_email: Contact email
        company_domain: Optional company domain
        subscription_tier: basic, premium, enterprise
        max_documents: Max documents allowed
        max_storage_mb: Max storage in MB
        
    Returns:
        dict with client_id, api_key, namespace
    """
    
    db = SessionLocal()
    
    try:
        # Generate unique client ID
        client_id = client_name.lower().replace(" ", "_").replace("'", "")[:30]
        
        # Check if exists
        existing = db.query(Client).filter(Client.client_id == client_id).first()
        if existing:
            raise ValueError(f"Client {client_id} already exists")
        
        # Generate API key
        api_key = generate_api_key()
        api_key_hash = hash_api_key(api_key)
        
        # Create namespace prefix
        namespace_prefix = f"client_{client_id}"
        
        # Create client record
        new_client = Client(
            client_id=client_id,
            client_name=client_name,
            api_key=api_key,
            api_key_hash=api_key_hash,
            namespace_prefix=namespace_prefix,
            subscription_tier=subscription_tier,
            max_documents=max_documents,
            max_storage_mb=max_storage_mb,
            is_active=True,
            contact_email=contact_email,
            company_domain=company_domain
        )
        
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        
        logger.info(f"✅ Created client: {client_name} ({client_id})")
        
        return {
            "client_id": client_id,
            "client_name": client_name,
            "api_key": api_key,
            "namespace_prefix": namespace_prefix,
            "subscription_tier": subscription_tier,
            "status": "active"
        }
        
    except Exception as e:
        logger.error(f"Failed to create client: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    # Example: Create demo clients
    
    # Client A: Acme Corporation
    acme = create_client(
        client_name="Acme Corporation",
        contact_email="admin@acme.com",
        company_domain="acme.com",
        subscription_tier="enterprise",
        max_documents=5000,
        max_storage_mb=50000
    )
    
    print("\n" + "="*60)
    print("✅ ACME CORPORATION ONBOARDED")
    print("="*60)
    print(f"Client ID: {acme['client_id']}")
    print(f"API Key: {acme['api_key']}")
    print(f"Namespace: {acme['namespace_prefix']}")
    print("="*60)
    
    # Client B: TechStart Inc
    techstart = create_client(
        client_name="TechStart Inc",
        contact_email="support@techstart.io",
        company_domain="techstart.io",
        subscription_tier="premium",
        max_documents=2000,
        max_storage_mb=20000
    )
    
    print("\n" + "="*60)
    print("✅ TECHSTART INC ONBOARDED")
    print("="*60)
    print(f"Client ID: {techstart['client_id']}")
    print(f"API Key: {techstart['api_key']}")
    print(f"Namespace: {techstart['namespace_prefix']}")
    print("="*60)
    
    print("\n💡 Save these API keys securely - they won't be shown again!")