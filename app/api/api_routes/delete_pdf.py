from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.toolkit.agent_toolkit import DeleteIndex, DeleteDocsFromIndex, DropIndex
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
    index_name: str = Body(..., description="Name of the Pinecone index. (Ensure the index name is in lowercase)"),
    doc_id: str = Body(None, description="Document ID (required for 'delete_docs' operation)."),
    operation: str = Body("delete_docs", description="Operation to perform: 'delete_docs' (default) or 'drop_index'")
):
    """
    Delete documents or entire index from Pinecone knowledge base.
    
    **Two operation modes:**
    - **delete_docs**: Delete specific document(s) by doc_id from the index. Requires doc_id parameter.
    - **drop_index**: Drop the entire Pinecone index. doc_id is ignored.
    """
    if not api_key:
        logger.warning("Unauthorized request: Missing or invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication key"
        )

    try:
        if operation == "delete_docs":
            if not doc_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="doc_id is required for 'delete_docs' operation"
                )
            await DeleteDocsFromIndex(index_name=index_name.lower(), doc_id=doc_id.lower())
            message = f"Document '{doc_id.lower()}' deleted successfully from index '{index_name.lower()}'."
        elif operation == "drop_index":
            await DropIndex(index_name=index_name.lower())
            message = f"Index '{index_name.lower()}' dropped entirely."
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid operation. Choose 'delete_docs' or 'drop_index'."
            )
        
        return DeleteKnowledgeBaseResponse(message=message)
        
    except Exception as e:
        logger.error(f"Error deleting from knowledge base: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )