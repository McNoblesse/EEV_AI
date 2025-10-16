from typing import Annotated
from fastapi import Security, status
from fastapi.security import APIKeyHeader
from fastapi.exceptions import HTTPException

from eev_configurations.config import settings

api_key_header = APIKeyHeader(name="api-key-header")

async def endpoint_auth(api_key:Annotated[str, Security(api_key_header)])->str:
    if api_key == settings.ENDPOINT_AUTH_KEY:
        return api_key
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

