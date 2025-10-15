from fastapi import HTTPException, Depends, status, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse 
from typing import Optional
import logging
import time
import jwt
from datetime import datetime, timedelta
from collections import defaultdict
import re
import os
from dotenv import load_dotenv
from fastapi import Security
from sqlalchemy.orm import Session
from model.database_models import Client
from config.database import SessionLocal

load_dotenv()

logger = logging.getLogger(__name__)

# API Key header
api_key_header = APIKeyHeader(name="tier_1_key_auth", auto_error=False)

# Tier-based API keys (store securely in production)
# Load API keys from .env
VALID_API_KEYS = {
    os.getenv("TIER1_API_KEY"): {"tier": 1, "name": "Tier 1 Client"},
    os.getenv("TIER2_API_KEY"): {"tier": 2, "name": "Tier 2 Client"},
    os.getenv("TIER3_API_KEY"): {"tier": 3, "name": "Tier 3 Client"},
    os.getenv("INTERNAL_API_KEY", "internal_system_key"): {"tier": 3, "name": "Internal System"}
}

def authenticate_api_key(api_key: Optional[str], min_tier: int = 1) -> str:
    """
    Authenticate API key with tier-based access.
    """
    if not api_key:
        logger.warning("API key missing")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    
    key_info = VALID_API_KEYS.get(api_key)
    if not key_info:
        logger.warning(f"Invalid API key: {api_key[:8]}...")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    if key_info["tier"] < min_tier:
        logger.warning(f"Insufficient tier for {key_info['name']}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient tier")
    
    logger.info(f"Authenticated: {key_info['name']} (Tier {key_info['tier']})")
    return api_key

async def AuthenticateTier1Model(tier_1_key_auth: str = Security(api_key_header)):
    """
    Authenticate and return API key with client context
    """
    if not tier_1_key_auth:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    # Validate API key (existing logic)
    from config.access_keys import accessKeys
    
    valid_keys = [
        accessKeys.TIER1_API_KEY,
        accessKeys.TIER2_API_KEY,
        accessKeys.TIER3_API_KEY
    ]
    
    if tier_1_key_auth not in valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return tier_1_key_auth

async def AuthenticateTier2Model(api_key: Optional[str] = Depends(api_key_header)):
    return authenticate_api_key(api_key, min_tier=2)

async def AuthenticateTier3Model(api_key: Optional[str] = Depends(api_key_header)):
    return authenticate_api_key(api_key, min_tier=3)

async def get_current_api_tier(api_key: Optional[str] = Depends(api_key_header)) -> int:
    if not api_key:
        return 0
    key_info = VALID_API_KEYS.get(api_key)
    return key_info["tier"] if key_info else 0

# Rate limiting (use Redis in production)
rate_limit_cache = defaultdict(list)

def rate_limit(requests_per_minute: int = 60):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            api_key = kwargs.get('api_key') or (args[0] if args else None)
            if not api_key:
                raise HTTPException(status_code=401, detail="API key required")
            
            current_time = time.time()
            window_start = current_time - 60
            rate_limit_cache[api_key] = [t for t in rate_limit_cache[api_key] if t > window_start]
            
            if len(rate_limit_cache[api_key]) >= requests_per_minute:
                logger.warning(f"Rate limit exceeded: {api_key[:8]}...")
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Rate limit: {requests_per_minute}/min")
            
            rate_limit_cache[api_key].append(current_time)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

async def security_middleware(request: Request, call_next):
    """
    Security middleware with checks and headers.
    """
    start_time = time.time()
    
    try:
        if request.method == "POST" and request.headers.get("content-length"):
            if int(request.headers.get("content-length", 0)) > 10 * 1024 * 1024:
                return JSONResponse(status_code=413, content={"error": "Payload too large"})
        
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Middleware error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Internal error"})
    
    # Security headers
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=()",
        "Access-Control-Allow-Origin": "*"
    })
    
    processing_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {processing_time:.3f}s")
    return response

def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    if not input_string:
        return ""
    sanitized = input_string[:max_length]
    dangerous_chars = ['<', '>', 'script', 'javascript', 'onload', 'onerror']
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized.strip()

def validate_session_id(session_id: str) -> bool:
    if not session_id or len(session_id) > 100:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', session_id))

def log_security_event(event_type: str, details: dict, request: Request = None):
    log_data = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details
    }
    if request:
        log_data.update({
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "path": request.url.path,
            "method": request.method
        })
    logger.warning(f"SECURITY_EVENT: {log_data}")

# JWT (for future use)
JWT_SECRET = os.getenv("JWT_SECRET")  # Loaded from .env
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

def create_jwt_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def validate_request_params(required_params: list = None, optional_params: list = None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if required_params:
                for param in required_params:
                    if param not in kwargs or kwargs[param] is None:
                        raise HTTPException(status_code=400, detail=f"Missing: {param}")
            if optional_params:
                for param in optional_params:
                    if param in kwargs and isinstance(kwargs[param], str) and len(kwargs[param]) > 1000:
                        raise HTTPException(status_code=400, detail=f"Too long: {param}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def get_client_from_api_key(api_key: str) -> Optional[dict]:
    """
    Extract client information from API key
    
    Returns:
        dict: {client_id, client_name, namespace_prefix}
    """
    db = SessionLocal()
    
    try:
        client = db.query(Client).filter(
            Client.api_key == api_key,
            Client.is_active == True
        ).first()
        
        if client:
            return {
                "client_id": client.client_id,
                "client_name": client.client_name,
                "namespace_prefix": client.namespace_prefix,
                "subscription_tier": client.subscription_tier
            }
        
        # Fallback to default client for backward compatibility
        return {
            "client_id": "default_client",
            "client_name": "Default Client",
            "namespace_prefix": "client_default",
            "subscription_tier": "basic"
        }
        
    finally:
        db.close()

def get_client_context(api_key: str = Security(api_key_header)) -> dict:
    """
    Dependency to inject client context into endpoints
    
    Usage:
        @router.post("/endpoint")
        async def endpoint(client: dict = Depends(get_client_context)):
            client_id = client["client_id"]
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    client_info = get_client_from_api_key(api_key)
    
    if not client_info:
        raise HTTPException(status_code=403, detail="Invalid or inactive client")
    
    return client_info
