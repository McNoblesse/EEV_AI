"""
Knowledge Base Management API
Handles document upload, processing, indexing, and management
"""

import os
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from security.authentication import AuthenticateTier1Model, get_client_context
from config.database import get_db
from model.database_models import DocumentUpload
from utils.document_processor import document_processor

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])
logger = logging.getLogger(__name__)

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# File size limits
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
MAX_FILES_PER_REQUEST = 5


@router.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    enable_ocr: bool = Form(False),
    client: dict = Depends(get_client_context),  # ✅ INJECT CLIENT CONTEXT
    db: Session = Depends(get_db)
):
    """
    Upload documents to client-specific knowledge base
    
    **Client Isolation**: Documents are stored in client-specific Pinecone namespace
    """
    
    client_id = client["client_id"]
    namespace_prefix = client["namespace_prefix"]
    
    logger.info(f"📁 Upload request from client: {client['client_name']} ({client_id})")
    
    # Validate file count
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES_PER_REQUEST} files allowed per request"
        )
    
    # Validate total size
    total_size = 0
    for file in files:
        # Read file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to start
        total_size += file_size
    
    if total_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Total file size exceeds {MAX_FILE_SIZE / 1024 / 1024}MB limit"
        )
    
    # Process each file
    uploaded_docs = []
    
    for file in files:
        try:
            # Generate unique filename
            file_ext = Path(file.filename).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            temp_file_path = UPLOAD_DIR / unique_filename
            
            # Validate file type
            allowed_extensions = ['.pdf', '.docx', '.txt', '.csv', '.doc']
            if file_ext not in allowed_extensions:
                logger.warning(f"Unsupported file type: {file.filename}")
                continue
            
            # Get file size
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            
            # Save file to disk first (THIS IS THE FIX)
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logger.info(f"Saved file to: {temp_file_path}")
            
            # Create database record
            doc_record = DocumentUpload(
                client_id=client_id,  # ✅ NEW
                client_name=client["client_name"],  # ✅ NEW
                filename=unique_filename,
                original_filename=file.filename,
                category=category,
                file_type=file_ext,
                file_size_bytes=file_size,
                status="pending",
                uploaded_by=client_id,  # ✅ CHANGED
                processing_started_at=datetime.utcnow()
            )
            
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)
            
            # ✅ PASS CLIENT CONTEXT TO BACKGROUND TASK
            background_tasks.add_task(
                process_document_background,
                doc_id=doc_record.id,
                file_path=str(temp_file_path),
                original_filename=file.filename,
                category=category,
                enable_ocr=enable_ocr,
                client_id=client_id,  # ✅ NEW
                namespace_prefix=namespace_prefix  # ✅ NEW
            )
            
            uploaded_docs.append({
                "id": doc_record.id,
                "filename": file.filename,
                "client_id": client_id,  # ✅ EXPOSE IN RESPONSE
                "status": "processing"
            })
            
            logger.info(f"Queued for processing: {file.filename} (ID: {doc_record.id})")
            
        except Exception as e:
            logger.error(f"Error uploading {file.filename}: {str(e)}", exc_info=True)
            continue
    
    if not uploaded_docs:
        raise HTTPException(
            status_code=400,
            detail="No valid files were uploaded"
        )
    
    return {
        "message": f"Successfully queued {len(uploaded_docs)} document(s) for client {client['client_name']}",
        "client_id": client_id,
        "documents": uploaded_docs
    }


async def process_document_background(
    doc_id: int,
    file_path: str,
    original_filename: str,
    category: str,
    enable_ocr: bool,
    client_id: str,  # ✅ NEW
    namespace_prefix: str  # ✅ NEW
):
    """
    Process document with client-specific namespace isolation
    """
    from config.database import SessionLocal
    db = SessionLocal()
    
    try:
        doc_record = db.query(DocumentUpload).filter(DocumentUpload.id == doc_id).first()
        if not doc_record:
            logger.error(f"Document {doc_id} not found")
            return
        
        doc_record.status = "processing"
        db.commit()
        
        start_time = datetime.utcnow()
        logger.info(f"Processing document {doc_id} for client {client_id}: {original_filename}")
        
        # Process document
        result = await document_processor.process_document(
            file_path=file_path,
            filename=original_filename,
            category=category,
            enable_ocr=enable_ocr
        )
        
        # ✅ CREATE CLIENT-SPECIFIC NAMESPACE
        namespace = f"{namespace_prefix}_{category.lower().replace(' ', '_')}"
        
        logger.info(f"📦 Storing in namespace: {namespace}")
        
        # ✅ STORE IN CLIENT-SPECIFIC PINECONE NAMESPACE
        vector_ids = await document_processor.store_in_vectordb(
            chunks=result["chunks"],
            metadata={
                "filename": original_filename,
                "category": category,
                "doc_id": doc_id,
                "client_id": client_id,  # ✅ ADD CLIENT ID TO METADATA
                "client_name": doc_record.client_name
            },
            namespace=namespace  # ✅ ISOLATED NAMESPACE
        )
        
        # Update record
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        doc_record.status = "indexed"
        doc_record.chunk_count = result["chunk_count"]
        doc_record.total_tokens = document_processor.estimate_tokens(result["text"])
        doc_record.text_preview = result["preview"]
        doc_record.vector_ids = vector_ids
        doc_record.namespace = namespace  # ✅ SAVE NAMESPACE
        doc_record.processing_completed_at = datetime.utcnow()
        doc_record.processing_time_ms = int(processing_time)
        doc_record.required_ocr = result["metadata"].get("ocr_used", False)
        doc_record.ocr_confidence = result["metadata"].get("ocr_confidence")
        doc_record.doc_metadata = result["metadata"]
        
        db.commit()
        
        logger.info(f"✅ Successfully processed {original_filename} for {client_id}: {result['chunk_count']} chunks in namespace {namespace}")
        
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {str(e)}", exc_info=True)
        
        doc_record = db.query(DocumentUpload).filter(DocumentUpload.id == doc_id).first()
        if doc_record:
            doc_record.status = "failed"
            doc_record.error_message = str(e)
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
    List all uploaded documents with optional filters
    
    Args:
        category: Filter by category
        status: Filter by status (pending/processing/indexed/failed)
        skip: Number of records to skip
        limit: Maximum records to return
        
    Returns:
        List of documents with metadata
    """
    query = db.query(DocumentUpload).filter(DocumentUpload.is_deleted == False)
    
    if category:
        query = query.filter(DocumentUpload.category == category)
    
    if status:
        query = query.filter(DocumentUpload.status == status)
    
    total = query.count()
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
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "chunk_count": doc.chunk_count,
                "processing_time_ms": doc.processing_time_ms,
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
    """Get detailed information about a specific document"""
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
        "metadata": document.doc_metadata,  # ✅ Return as "metadata" in JSON
        "error_message": document.error_message
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    api_key: str = Depends(AuthenticateTier1Model),
    db: Session = Depends(get_db)
):
    """
    Soft delete a document (marks as deleted, doesn't remove from DB)
    
    Args:
        document_id: Document ID to delete
        
    Returns:
        Success message
    """
    document = db.query(DocumentUpload).filter(
        DocumentUpload.id == document_id,
        DocumentUpload.is_deleted == False
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Soft delete
    document.is_deleted = True
    document.deleted_at = datetime.utcnow()
    db.commit()
    
    # TODO: Also delete from Pinecone vector store
    # if document.vector_ids:
    #     await document_processor.delete_from_vectordb(document.vector_ids)
    
    logger.info(f"Deleted document {document_id}: {document.original_filename}")
    
    return {
        "message": f"Document {document.original_filename} deleted successfully",
        "document_id": document_id
    }