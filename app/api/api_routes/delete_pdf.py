from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.toolkit.agent_toolkit import DeleteIndex
from app.api.model.schema import DeleteKnowledgeBaseResponse

from fastapi import (
    APIRouter,
    Depends,
    HTTPException, 
    status , 
    Body,
    )

router = APIRouter(prefix="/delete_pdf", 
                   tags=["Knowledge Base Endpoint"])

@router.post("/delete_knowledge_base", response_model=DeleteKnowledgeBaseResponse)
async def delete_knowledge_base(
    api_key=Depends(endpoint_auth),
    index_name: str = Body(..., description="Name of the Pinecone index to delete. (Ensure the index name is in lowercase)"),
    doc_id: str = Body(..., description="Document ID associated with the knowledge base.")
):
    if not api_key:
        logger.warning("Unauthorized request: Missing or invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication key"
        )

    try:
        await DeleteIndex(index_name=index_name.lower(), doc_id=doc_id.lower())
        return DeleteKnowledgeBaseResponse(message=f"Knowledge base deleted successfully id = {doc_id.lower()}.")
        
    except Exception as e:
        logger.error(f"Error deleting knowledge base: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting pdf with id = {doc_id}"
        )