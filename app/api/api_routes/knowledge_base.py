from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.api.model.schema import CreateKnowledgeBaseResponse
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

@router.post("/create_knowledge_base", response_model=CreateKnowledgeBaseResponse)
async def create_knowledge_base(
    api_key=Depends(endpoint_auth),
    index_name: str = Body(..., description="Name of the Pinecone index to create. (Ensure the index name is in lowercase)"),
    doc_ids: List[str] = Body(..., description="List of Document IDs associated with the knowledge base."),
    data: List[UploadFile] = File(..., description="Files to upload for knowledge base.")
):
    if not api_key:
        logger.warning("Unauthorized request: Missing or invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication key"
        )

    results = []
    
    doc_ids = doc_ids[0].split(",")
     
    for file, doc_id in zip(data, doc_ids):
        try:
            extracted_data = await ExtractAndSplitContentFromFile(file, doc_id=doc_id)
            await EmbeddDoc(index_name=index_name.lower(), extracted_data=extracted_data)
            results.append({"file": file.filename, "status": "success", "doc_id": doc_id})
            logger.info(f"Knowledge base created for file {file.filename} with doc_id {doc_id}")
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
            results.append({"file": file.filename, "status": "failed", "error": str(e)})
    return CreateKnowledgeBaseResponse(results=results)