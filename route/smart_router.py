"""
Smart Router: Automatically routes queries to the appropriate tier
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
import logging

from security.authentication import get_client_context, build_namespace
from model.schema import RequestPayload, PayloadResponse
from config.database import get_db
from utils.complexity_analyzer import complexity_analyzer

# Import tier handlers
from route.tier_1_model import tier_1_handler
from route.tier_2_model import tier_2_handler
from route.tier_3_model import tier_3_model_handler

router = APIRouter(prefix="/model", tags=["Smart Router"])
logger = logging.getLogger(__name__)


@router.post("/auto_route", response_model=PayloadResponse)
async def auto_route_handler(
    data: RequestPayload,
    client: dict = Depends(get_client_context),  # ✅ INJECT CLIENT
    db: Session = Depends(get_db)
):
    """
    Smart routing with client-specific knowledge base access
    """
    
    client_id = client["client_id"]
    category = getattr(data, 'category', None)  # ✅ EXTRACT CATEGORY
    
    logger.info(f"Auto-routing query for client: {client['client_name']} ({client_id}), category: {category}")
    
    try:
        # Fast complexity analysis
        complexity_result = complexity_analyzer.analyze_fast(data.user_query)
        
        logger.info(f"Routing to {complexity_result.tier} for client {client_id} (score={complexity_result.score})")
        
        # Route to appropriate tier (all will have client context + category)
        if complexity_result.tier == 'tier1':
            return await tier_1_handler(data, client, db)
        
        elif complexity_result.tier == 'tier2':
            complexity_result = await complexity_analyzer.analyze_with_llm(data.user_query)
            
            if complexity_result.score < 31:
                return await tier_1_handler(data, client, db)
            elif complexity_result.score > 70:
                return tier_3_model_handler(data, client, db)
            else:
                return await tier_2_handler(data, client, db)  # ✅ Category passed via data
        
        else:  # tier3
            return tier_3_model_handler(data, client, db)
    
    except Exception as e:
        logger.error(f"Auto-routing failed for client {client_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")