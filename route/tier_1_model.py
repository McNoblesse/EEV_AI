from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from security.authentication import AuthenticateTier1Model
from model.schema import RequestPayload, PayloadResponse
from langchain_core.messages import HumanMessage
from utils.tier_1_utils import graph

router = APIRouter(
    prefix="/model", 
    tags=["Tier 1 model"]
)

@router.post("/tier_1_model", response_model=PayloadResponse)
async def tier_1_model_handler(
    data: RequestPayload, 
    api_key: Annotated[str, Depends(AuthenticateTier1Model)]
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key"
        )

    config = {
        "configurable": {
            "thread_id": data.session_id
        }
    }

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=data.user_query)]},
        config=config
    )

    return PayloadResponse(
        session_id=data.session_id,
        bot_response=result["messages"][-1].content 
    )
