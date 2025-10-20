from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.toolkit.agent_toolkit import ExtractAndSplitContentFromFile, EmbeddDoc

from typing import List
from fastapi import (
    APIRouter,
    Depends,
    HTTPException, 
    status , 
    Body,
    UploadFile,
    File
    )

router = APIRouter(prefix="/knowledge_base", 
                   tags=["Knowledge Base Endpoint"])

@router.post("/create_knowledge_base")
async def create_knowledge_base(
    api_key=Depends(endpoint_auth),
    index_name: str = Body(..., description="Name of the Pinecone index to create. (Ensure the index name is in lowercase)"),
    data: List[UploadFile] = File(..., description="Files to upload for knowledge base.")
):
    if not api_key:
        logger.warning("Unauthorized request: Missing or invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication key"
        )

    results = []
    for file in data:
        try:
            extracted_data = await ExtractAndSplitContentFromFile(file)
            await EmbeddDoc(index_name=index_name.lower(), extracted_data=extracted_data)
            results.append({"file": file.filename, "status": "success"})
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
            results.append({"file": file.filename, "status": "failed", "error": str(e)})
    return {"results": results}