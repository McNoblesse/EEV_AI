"""
Knowledge Base Management API
Handles document upload, processing, indexing, and management
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import uuid
from datetime import datetime
import os

from config.database import get_db
from security.authentication import AuthenticateTier1Model
from model.database_models import DocumentUpload
from utils.document_processor import document_processor
from utils.tools import vectorstore, embed_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["Knowledge Base"])


@router.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    enable_ocr: bool = Form(True),
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    Upload and process documents for knowledge base
    
    **Limits**:
    - Maximum 5 files per request
    - Combined size limit: 200MB
    - Individual file limit: 50MB
    """
    
    # Validate file count
    if len(files) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 files allowed per upload. Please split your upload into multiple requests."
        )
    
    # Calculate total size
    total_size = 0
    for file in files:
        content = await file.read()
        total_size += len(content)
        await file.seek(0)  # Reset for processing
    
    # Validate total size (200MB = 209,715,200 bytes)
    if total_size > 200 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Total upload size ({total_size / 1024 / 1024:.1f}MB) exceeds 200MB limit"
        )
    
    if not category or not category.strip():
        raise HTTPException(status_code=400, detail="Category is required")
    
    results = []
    
    for file in files:
        try:
            # Validate file size (50MB limit)
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > 50 * 1024 * 1024:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": "File size exceeds 50MB limit"
                })
                continue
            
            # Reset file pointer
            await file.seek(0)
            
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Create database record
            doc_record = DocumentUpload(
                filename=unique_filename,
                original_filename=file.filename,
                category=category.strip(),
                file_type=file_extension,
                file_size_bytes=file_size,
                status="pending",
                uploaded_by=api_key[:10] if api_key else "anonymous"
            )
            
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)
            
            # Process document in background
            background_tasks.add_task(
                process_document_background,
                doc_id=doc_record.id,
                file=file,
                category=category,
                enable_ocr=enable_ocr
            )
            
            results.append({
                "id": doc_record.id,
                "filename": file.filename,
                "status": "processing",
                "message": "Document uploaded and queued for processing"
            })
            
        except Exception as e:
            logger.error(f"Error uploading {file.filename}: {str(e)}")
            results.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "uploaded_documents": results,
        "total_files": len(files),
        "successful": len([r for r in results if r["status"] == "processing"]),
        "failed": len([r for r in results if r["status"] == "failed"])
    }


async def process_document_background(
    doc_id: int,
    file: UploadFile,
    category: str,
    enable_ocr: bool
):
    """
    Background task to process uploaded document
    """
    from config.database import SessionLocal
    db = SessionLocal()
    
    try:
        # Get document record
        doc_record = db.query(DocumentUpload).filter(DocumentUpload.id == doc_id).first()
        if not doc_record:
            logger.error(f"Document record {doc_id} not found")
            return
        
        # Update status
        doc_record.status = "processing"
        doc_record.processing_started_at = datetime.utcnow()
        db.commit()
        
        start_time = datetime.utcnow()
        
        # Process document
        result = await document_processor.process_document(
            file=file,
            category=category,
            enable_ocr=enable_ocr
        )
        
        # Store chunks in Pinecone
        vector_ids = []
        namespace = f"kb_{category.lower().replace(' ', '_')}"
        
        for i, chunk in enumerate(result["chunks"]):
            # Create metadata for each chunk
            metadata = {
                "source": doc_record.original_filename,
                "category": category,
                "chunk_index": i,
                "total_chunks": result["chunk_count"],
                "upload_date": doc_record.upload_date.isoformat(),
                "document_id": doc_id,
                "file_type": result["file_type"],
                **result["metadata"]
            }
            
            # Add to vector store
            try:
                ids = vectorstore.add_texts(
                    texts=[chunk],
                    metadatas=[metadata],
                    namespace=namespace
                )
                if ids:
                    vector_ids.extend(ids)
            except Exception as e:
                logger.error(f"Failed to add chunk {i} to vector store: {str(e)}")
        
        # Update document record
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        doc_record.status = "indexed"
        doc_record.chunk_count = result["chunk_count"]
        doc_record.total_tokens = document_processor.estimate_tokens(result["text"])
        doc_record.text_preview = result["preview"]
        doc_record.vector_ids = vector_ids
        doc_record.namespace = namespace
        doc_record.processing_completed_at = datetime.utcnow()
        doc_record.processing_time_ms = int(processing_time)
        doc_record.required_ocr = result["metadata"].get("ocr_used", False)
        doc_record.ocr_confidence = result["metadata"].get("ocr_confidence")
        doc_record.metadata = result["metadata"]
        
        db.commit()
        
        logger.info(
            f"Successfully processed document {doc_id}: "
            f"{result['chunk_count']} chunks, {processing_time:.0f}ms"
        )
        
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {str(e)}")
        
        # Update status to failed
        if doc_record:
            doc_record.status = "failed"
            doc_record.error_message = str(e)
            doc_record.processing_completed_at = datetime.utcnow()
            db.commit()
    
    finally:
        db.close()


@router.get("/documents")
async def list_documents(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    List uploaded documents with optional filtering
    
    Args:
        category: Filter by document category
        status: Filter by processing status (pending, processing, indexed, failed)
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        
    Returns:
        List of documents with metadata
    """
    query = db.query(DocumentUpload).filter(DocumentUpload.is_deleted == False)
    
    if category:
        query = query.filter(DocumentUpload.category == category)
    
    if status:
        query = query.filter(DocumentUpload.status == status)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    documents = query.order_by(DocumentUpload.upload_date.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_filename,
                "category": doc.category,
                "file_type": doc.file_type,
                "file_size_bytes": doc.file_size_bytes,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "processing_time_ms": doc.processing_time_ms,
                "required_ocr": doc.required_ocr,
                "text_preview": doc.text_preview,
                "error_message": doc.error_message
            }
            for doc in documents
        ]
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific document
    
    Args:
        document_id: Document ID
        
    Returns:
        Document details including metadata
    """
    document = db.query(DocumentUpload).filter(
        DocumentUpload.id == document_id,
        DocumentUpload.is_deleted == False
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": document.id,
        "filename": document.original_filename,
        "category": document.category,
        "file_type": document.file_type,
        "file_size_bytes": document.file_size_bytes,
        "status": document.status,
        "upload_date": document.upload_date.isoformat() if document.upload_date else None,
        "uploaded_by": document.uploaded_by,
        "chunk_count": document.chunk_count,
        "total_tokens": document.total_tokens,
        "text_preview": document.text_preview,
        "namespace": document.namespace,
        "processing_started_at": document.processing_started_at.isoformat() if document.processing_started_at else None,
        "processing_completed_at": document.processing_completed_at.isoformat() if document.processing_completed_at else None,
        "processing_time_ms": document.processing_time_ms,
        "required_ocr": document.required_ocr,
        "ocr_confidence": document.ocr_confidence,
        "metadata": document.metadata,
        "error_message": document.error_message
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    Delete a document from the knowledge base
    
    Performs soft delete and removes vectors from Pinecone
    
    Args:
        document_id: Document ID to delete
        
    Returns:
        Deletion confirmation
    """
    document = db.query(DocumentUpload).filter(
        DocumentUpload.id == document_id,
        DocumentUpload.is_deleted == False
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Delete vectors from Pinecone
        if document.vector_ids and document.namespace:
            try:
                from pinecone import Pinecone
                from config.access_keys import accessKeys

                pc = Pinecone(api_key=accessKeys.PINECONE_API_KEY)
                index = pc.Index('eev-ai-unstructured-data')
                index.delete(
                    ids=document.vector_ids,
                    namespace=document.namespace
                )
                logger.info(f"Deleted {len(document.vector_ids)} vectors from Pinecone")
            except Exception as e:
                logger.error(f"Failed to delete vectors from Pinecone: {str(e)}")
                # Continue with soft delete even if Pinecone deletion fails
        
        # Soft delete in database
        document.is_deleted = True
        document.deleted_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Document deleted successfully",
            "document_id": document_id,
            "filename": document.original_filename,
            "vectors_deleted": len(document.vector_ids) if document.vector_ids else 0
        }
        
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/categories")
async def list_categories(
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    Get list of all document categories
    
    Returns:
        List of unique categories with document counts
    """
    from sqlalchemy import func
    
    categories = db.query(
        DocumentUpload.category,
        func.count(DocumentUpload.id).label('count')
    ).filter(
        DocumentUpload.is_deleted == False
    ).group_by(
        DocumentUpload.category
    ).all()
    
    return {
        "categories": [
            {
                "name": cat.category,
                "document_count": cat.count
            }
            for cat in categories
        ]
    }


@router.get("/stats")
async def get_stats(
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    Get knowledge base statistics
    
    Returns:
        Overall statistics about the knowledge base
    """
    from sqlalchemy import func
    
    stats = {
        "total_documents": db.query(DocumentUpload).filter(
            DocumentUpload.is_deleted == False
        ).count(),
        "by_status": {},
        "by_file_type": {},
        "total_chunks": db.query(func.sum(DocumentUpload.chunk_count)).filter(
            DocumentUpload.is_deleted == False,
            DocumentUpload.status == "indexed"
        ).scalar() or 0,
        "total_size_bytes": db.query(func.sum(DocumentUpload.file_size_bytes)).filter(
            DocumentUpload.is_deleted == False
        ).scalar() or 0
    }
    
    # Status breakdown
    status_counts = db.query(
        DocumentUpload.status,
        func.count(DocumentUpload.id)
    ).filter(
        DocumentUpload.is_deleted == False
    ).group_by(DocumentUpload.status).all()
    
    stats["by_status"] = {status: count for status, count in status_counts}
    
    # File type breakdown
    type_counts = db.query(
        DocumentUpload.file_type,
        func.count(DocumentUpload.id)
    ).filter(
        DocumentUpload.is_deleted == False
    ).group_by(DocumentUpload.file_type).all()
    
    stats["by_file_type"] = {file_type: count for file_type, count in type_counts}
    
    return stats