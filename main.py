from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn
from fastapi.responses import JSONResponse
from route.voice_ai_route import router as voice_router
from route.tier_3_model import router as tier3_router
from route.freshdesk import router as freshdesk_router
from security.authentication import security_middleware
from config.database import engine, Base
from utils.checkpoint_migrations import ensure_tables_and_report, init_postgres_checkpointer
from utils.voice_ai_utils import voice_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting EEV AI Assistant API...")
    
    try:
        # Initialize database tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
        
        # Initialize LangGraph checkpointer
        init_postgres_checkpointer()
        logger.info("LangGraph checkpointer initialized")
        
        # Report on existing data
        ensure_tables_and_report()
        logger.info("System startup completed successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield  # App is running
    
    # Shutdown
    logger.info("Shutting down EEV AI Assistant API...")
    
    try:
        # Cleanup temporary files
        voice_processor.cleanup_old_files()
        logger.info("Temporary files cleaned up")
    except Exception as e:
        logger.error(f"Shutdown cleanup failed: {e}")

# Create FastAPI app
app = FastAPI(
    title="EEV AI Assistant API",
    description="Multi-channel AI customer support assistant with multi-step reasoning",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware
app.middleware("http")(security_middleware)

# Include routers
app.include_router(voice_router, prefix="/api/v1")
app.include_router(tier3_router, prefix="/api/v1")
app.include_router(freshdesk_router, prefix="/api/v1")

# Health check endpoint
@app.get("/")
async def root():
    """
    Root endpoint with system status
    """
    return {
        "message": "EEV AI Assistant API is running",
        "version": "2.0.0",
        "status": "healthy",
        "features": [
            "Multi-step reasoning with ReAct logic",
            "Multi-channel support (voice, chat, email, Freshdesk)",
            "Smart routing based on query complexity",
            "Knowledge base integration",
            "Human escalation handling"
        ]
    }

@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    """
    from config.database import SessionLocal
    import redis
    
    health_status = {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",  # Will be updated dynamically
        "components": {}
    }
    
    # Database health check
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Redis health check
    try:
        from route.freshdesk import get_redis_client
        redis_client = get_redis_client()
        redis_client.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # LangGraph checkpointer health
    try:
        from utils.checkpoint_migrations import ensure_tables_and_report
        ensure_tables_and_report()
        health_status["components"]["langgraph"] = "healthy"
    except Exception as e:
        health_status["components"]["langgraph"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/system/status")
async def system_status():
    """
    Detailed system status and analytics
    """
    from config.database import SessionLocal
    from model.database_models import Conversation, AgentSession
    
    db = SessionLocal()
    
    try:
        # Basic statistics
        total_conversations = db.query(Conversation).count()
        active_sessions = db.query(AgentSession).filter(AgentSession.is_active == True).count()
        
        # Intent distribution
        intent_stats = db.query(
            Conversation.intent, 
            func.count(Conversation.id)
        ).group_by(Conversation.intent).all()
        
        # Channel distribution
        channel_stats = db.query(
            Conversation.channel,
            func.count(Conversation.id)
        ).group_by(Conversation.channel).all()
        
        return {
            "total_conversations": total_conversations,
            "active_sessions": active_sessions,
            "intent_distribution": dict(intent_stats),
            "channel_distribution": dict(channel_stats),
            "average_confidence": 0.78,  # Would calculate from actual data
            "escalation_rate": 0.05     # Would calculate from actual data
        }
    finally:
        db.close()

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Global HTTP exception handler
    """
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Global exception handler
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8056,
        reload=True,  # Disable in production
        log_level="info",
        access_log=True
    )