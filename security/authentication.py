from typing import Annotated
from fastapi.security import APIKeyHeader
from fastapi import Depends, HTTPException, status

from config.access_keys import accessKeys

apiKeyHeader_1 = APIKeyHeader(
    name="tier_1_key_auth", 
    description="This key only unlocks tier one model"
)

async def AuthenticateTier1Model(
    api_key: Annotated[str, Depends(apiKeyHeader_1)]
):
    if api_key != accessKeys.tier_1_auth_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Tier 1 API Key",
        )
    return api_key
