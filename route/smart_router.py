"""
Smart Router: Automatically routes queries to the appropriate tier
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
import logging

from security.authentication import AuthenticateTier1Model
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
    api_key: Annotated[str, Depends(AuthenticateTier1Model)],
    db: Session = Depends(get_db)
):
    """
    Automatically route query to appropriate tier based on complexity
    
    - Tier 1 (0-30): Simple queries, greetings, basic FAQs
    - Tier 2 (31-70): Moderate complexity, retrieval + analysis
    - Tier 3 (71-100): Complex multi-step reasoning
    """
    
    try:
        # Fast complexity analysis
        complexity_result = complexity_analyzer.analyze_fast(data.user_query)
        
        logger.info(f"Auto-routing query with complexity={complexity_result.score} to {complexity_result.tier}")
        
        # Route based on tier
        if complexity_result.tier == 'tier1':
            return await tier_1_handler(data, api_key, db)
        
        elif complexity_result.tier == 'tier2':
            # Use LLM for more accurate analysis
            complexity_result = await complexity_analyzer.analyze_with_llm(data.user_query)
            
            # Re-check after LLM analysis
            if complexity_result.score < 31:
                return await tier_1_handler(data, api_key, db)
            elif complexity_result.score > 70:
                return tier_3_model_handler(data, api_key, db)
            else:
                return await tier_2_handler(data, api_key, db)
        
        else:  # tier3
            return tier_3_model_handler(data, api_key, db)
    
    except Exception as e:
        logger.error(f"Auto-routing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")