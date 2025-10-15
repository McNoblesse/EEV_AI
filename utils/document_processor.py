"""
Document Processing Utilities for Knowledge Base
Handles extraction, chunking, and embedding of various document types
"""

import io
import os
import logging
import csv
import tempfile
from typing import Tuple, List, Dict, Any, Optional
from fastapi import UploadFile
import PyPDF2
from docx import Document
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pathlib import Path

logger = logging.getLogger(__name__)

# Configure Tesseract path (Windows-specific, adjust if needed)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class DocumentProcessor:
    """Process various document types for knowledge base ingestion"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.csv', '.docx', '.doc'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        enable_ocr: bool = True
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.enable_ocr = enable_ocr
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    async def process_document(
        self,
        file_path: str,  # ✅ CHANGED: Accept file path
        filename: str,
        category: str,
        enable_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        Process document from file path
        
        Args:
            file_path: Path to file on disk
            filename: Original filename
            category: Document category
            enable_ocr: Whether to use OCR
            
        Returns:
            Dict with text, chunks, metadata
        """
        file_ext = Path(filename).suffix.lower()
        
        try:
            logger.info(f"Processing {file_ext} file: {filename}")
            
            # Read file based on extension
            if file_ext == '.pdf':
                text = await self._process_pdf(file_path, enable_ocr)
            elif file_ext in ['.docx', '.doc']:
                text = await self._process_docx(file_path)
            elif file_ext == '.txt':
                text = await self._process_txt(file_path)
            elif file_ext == '.csv':
                text = await self._process_csv(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            # Create chunks
            chunks = self._create_chunks(text, chunk_size=1000, overlap=200)
            
            # Generate preview
            preview = text[:500] if len(text) > 500 else text
            
            return {
                "text": text,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "preview": preview,
                "metadata": {
                    "filename": filename,
                    "category": category,
                    "file_type": file_ext,
                    "ocr_used": enable_ocr,
                    "ocr_confidence": None
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {str(e)}", exc_info=True)
            raise
    
    async def _process_pdf(self, file_path: str, enable_ocr: bool) -> str:
        """Extract text from PDF"""
        text = ""
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # TODO: Add OCR if enable_ocr and text is empty
        
        return text.strip()
    
    async def _process_docx(self, file_path: str) -> str:
        """Extract text from DOCX"""
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()
    
    async def _process_txt(self, file_path: str) -> str:
        """Read text file"""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    
    async def _process_csv(self, file_path: str) -> str:
        """Convert CSV to text"""
        text_parts = []
        
        with open(file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                row_text = ", ".join([f"{k}: {v}" for k, v in row.items()])
                text_parts.append(row_text)
        
        return "\n".join(text_parts)
    
    def _create_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    async def store_in_vectordb(
        self, 
        chunks: List[str], 
        metadata: Dict,
        namespace: str = "default"  # ✅ ADD NAMESPACE PARAMETER
    ) -> List[str]:
        """
        Store chunks in Pinecone with client-specific namespace
        
        Args:
            chunks: Text chunks to embed and store
            metadata: Document metadata (must include client_id)
            namespace: Pinecone namespace for isolation
            
        Returns:
            List of vector IDs
        """
        from utils.tools import vectorstore, embed_model
        
        try:
            logger.info(f"Storing {len(chunks)} chunks in namespace: {namespace}")
            
            # Generate embeddings for all chunks
            vector_ids = []
            
            for i, chunk in enumerate(chunks):
                # Create metadata for this chunk
                chunk_metadata = {
                    **metadata,
                    "chunk_index": i,
                    "chunk_text": chunk[:200],  # Preview
                    "namespace": namespace
                }
                
                # Add to Pinecone with namespace
                result = vectorstore.add_texts(
                    texts=[chunk],
                    metadatas=[chunk_metadata],
                    namespace=namespace  # ✅ ISOLATE BY NAMESPACE
                )
                
                if result:
                    vector_ids.extend(result)
            
            logger.info(f"✅ Stored {len(vector_ids)} vectors in namespace {namespace}")
            
            return vector_ids
            
        except Exception as e:
            logger.error(f"Failed to store in vector DB: {e}", exc_info=True)
            raise


# Singleton instance
document_processor = DocumentProcessor(
    chunk_size=1000,
    chunk_overlap=200,
    enable_ocr=True
)
