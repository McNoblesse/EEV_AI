# Knowledge Base Document Ingestion System

## Overview

A complete document ingestion pipeline for the EEV AI Assistant that supports uploading, processing, and indexing various document types into a Pinecone vector store for intelligent retrieval.

## Features

### ✅ Supported Document Types
- **PDF** (text-based and scanned with OCR)
- **CSV** (converted to structured text)
- **TXT** (plain text files)
- **DOCX** (Microsoft Word documents)

### ✅ Capabilities
- **Automatic OCR**: Scanned PDFs are automatically processed with Tesseract OCR
- **Intelligent Chunking**: Documents are split into optimal chunks (1000 chars with 200 overlap)
- **Vector Indexing**: Automatic embedding and indexing in Pinecone
- **Background Processing**: Large files are processed asynchronously
- **Comprehensive Metadata**: Tracks processing status, chunk counts, OCR confidence, etc.
- **Category Management**: Organize documents by category
- **Soft Deletion**: Documents can be deleted while maintaining audit trail

## API Endpoints

### 1. Upload Documents

**Endpoint**: `POST /api/v1/knowledge-base/upload`

**Description**: Upload and process documents for the knowledge base

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/knowledge-base/upload" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "files=@document1.pdf" \
  -F "files=@document2.csv" \
  -F "category=Product Documentation" \
  -F "enable_ocr=true"
```

**Parameters**:
- `files` (required): One or more files to upload
- `category` (required): Document category for organization
- `enable_ocr` (optional, default: true): Enable OCR for scanned PDFs

**Response**:
```json
{
  "uploaded_documents": [
    {
      "id": 1,
      "filename": "document1.pdf",
      "status": "processing",
      "message": "Document uploaded and queued for processing"
    }
  ],
  "total_files": 2,
  "successful": 2,
  "failed": 0
}
```

### 2. List Documents

**Endpoint**: `GET /api/v1/knowledge-base/documents`

**Description**: List all uploaded documents with filtering

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/knowledge-base/documents?category=Product%20Documentation&status=indexed&skip=0&limit=10" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Parameters**:
- `category` (optional): Filter by category
- `status` (optional): Filter by status (pending, processing, indexed, failed)
- `skip` (optional, default: 0): Pagination offset
- `limit` (optional, default: 100): Maximum results

**Response**:
```json
{
  "total": 50,
  "skip": 0,
  "limit": 10,
  "documents": [
    {
      "id": 1,
      "filename": "product_guide.pdf",
      "category": "Product Documentation",
      "file_type": ".pdf",
      "file_size_bytes": 524288,
      "status": "indexed",
      "chunk_count": 25,
      "upload_date": "2025-01-10T12:30:00Z",
      "processing_time_ms": 5432,
      "required_ocr": false,
      "text_preview": "This is a comprehensive guide...",
      "error_message": null
    }
  ]
}
```

### 3. Get Document Details

**Endpoint**: `GET /api/v1/knowledge-base/documents/{document_id}`

**Description**: Get detailed information about a specific document

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/knowledge-base/documents/1" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "id": 1,
  "filename": "product_guide.pdf",
  "category": "Product Documentation",
  "file_type": ".pdf",
  "file_size_bytes": 524288,
  "status": "indexed",
  "upload_date": "2025-01-10T12:30:00Z",
  "uploaded_by": "api_key_12",
  "chunk_count": 25,
  "total_tokens": 8500,
  "text_preview": "This is a comprehensive guide...",
  "namespace": "kb_product_documentation",
  "processing_started_at": "2025-01-10T12:30:05Z",
  "processing_completed_at": "2025-01-10T12:30:10Z",
  "processing_time_ms": 5432,
  "required_ocr": false,
  "ocr_confidence": null,
  "metadata": {
    "page_count": 10,
    "extraction_method": "text"
  },
  "error_message": null
}
```

### 4. Delete Document

**Endpoint**: `DELETE /api/v1/knowledge-base/documents/{document_id}`

**Description**: Delete a document from the knowledge base (soft delete + vector removal)

**Request**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/knowledge-base/documents/1" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "message": "Document deleted successfully",
  "document_id": 1,
  "filename": "product_guide.pdf",
  "vectors_deleted": 25
}
```

### 5. List Categories

**Endpoint**: `GET /api/v1/knowledge-base/categories`

**Description**: Get all document categories with counts

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/knowledge-base/categories" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "categories": [
    {
      "name": "Product Documentation",
      "document_count": 25
    },
    {
      "name": "Customer Support",
      "document_count": 15
    }
  ]
}
```

### 6. Get Statistics

**Endpoint**: `GET /api/v1/knowledge-base/stats`

**Description**: Get overall knowledge base statistics

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/knowledge-base/stats" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "total_documents": 40,
  "by_status": {
    "indexed": 35,
    "processing": 3,
    "failed": 2
  },
  "by_file_type": {
    ".pdf": 20,
    ".docx": 10,
    ".csv": 5,
    ".txt": 5
  },
  "total_chunks": 850,
  "total_size_bytes": 52428800
}
```

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (for scanned PDFs)

**Windows**:
```bash
# Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
# Install to: C:\Program Files\Tesseract-OCR
# Add to PATH
```

**Linux**:
```bash
sudo apt-get install tesseract-ocr
sudo apt-get install poppler-utils  # for pdf2image
```

**macOS**:
```bash
brew install tesseract
brew install poppler
```

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# LangSmith Monitoring (Optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=eev-ai-production
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Existing variables
PINECONE_API_KEY=your_pinecone_key
OPENAI_API_KEY=your_openai_key
...
```

### 4. Run Database Migration

```bash
# Using Python directly (if alembic command not available)
python -c "from config.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

Or create tables manually by running the migration SQL:

```sql
-- See alembic/versions/001_document_uploads.py for full SQL
CREATE TABLE document_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    ...
);
```

### 5. Start the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Architecture

### Document Processing Flow

```
User Upload → Validation → Database Record (pending) 
                    ↓
            Background Task
                    ↓
    Extract Text (OCR if needed)
                    ↓
         Chunk Text (1000 chars)
                    ↓
    Generate Embeddings (Google Gemini)
                    ↓
       Store in Pinecone + Metadata
                    ↓
    Update DB (status: indexed)
```

### Database Schema

**Table**: `document_uploads`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| filename | String | Unique filename (UUID) |
| original_filename | String | Original upload name |
| category | String | Document category |
| file_type | String | File extension (.pdf, .csv, etc.) |
| file_size_bytes | Integer | File size |
| status | String | pending/processing/indexed/failed |
| chunk_count | Integer | Number of chunks created |
| total_tokens | Integer | Estimated token count |
| text_preview | Text | First 500 chars |
| vector_ids | JSON | Pinecone vector IDs |
| namespace | String | Pinecone namespace |
| processing_time_ms | Integer | Processing duration |
| required_ocr | Boolean | Whether OCR was used |
| ocr_confidence | Float | OCR confidence score |
| metadata | JSON | Additional metadata |
| is_deleted | Boolean | Soft delete flag |
| upload_date | Timestamp | Upload timestamp |

## Usage Examples

### Python Client

```python
import requests

BASE_URL = "http://localhost:8000"
API_KEY = "your_api_key"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Upload document
with open("document.pdf", "rb") as f:
    files = {"files": f}
    data = {
        "category": "Product Docs",
        "enable_ocr": "true"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/knowledge-base/upload",
        headers=headers,
        files=files,
        data=data
    )
    print(response.json())

# List documents
response = requests.get(
    f"{BASE_URL}/api/v1/knowledge-base/documents",
    headers=headers,
    params={"category": "Product Docs", "status": "indexed"}
)
print(response.json())
```

### JavaScript/TypeScript

```typescript
const formData = new FormData();
formData.append('files', fileInput.files[0]);
formData.append('category', 'Product Documentation');
formData.append('enable_ocr', 'true');

const response = await fetch('http://localhost:8000/api/v1/knowledge-base/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${apiKey}`
  },
  body: formData
});

const result = await response.json();
console.log(result);
```

## Monitoring & Debugging

### LangSmith Integration

All document processing operations are traced in LangSmith when enabled:

1. **Set environment variables** (see Setup section)
2. **View traces** at https://smith.langchain.com
3. **Monitor**:
   - Processing times
   - Embedding generation
   - Vector store operations
   - Error rates

### Logs

All operations are logged to:
- **Console output**
- **app.log** file

Log levels:
- `INFO`: Successful operations
- `WARNING`: Recoverable issues (e.g., OCR fallback)
- `ERROR`: Failed operations

### Common Issues

**Issue**: OCR not working
```
Solution: Ensure Tesseract is installed and in PATH
Windows: Set pytesseract.pytesseract.tesseract_cmd in utils/document_processor.py
```

**Issue**: "No module named 'docx'"
```
Solution: pip install python-docx
```

**Issue**: "pdf2image requires poppler"
```
Solution: Install poppler-utils (Linux) or download poppler binaries (Windows)
```

## Performance

### Benchmarks

| Document Type | Size | Processing Time | Chunks |
|--------------|------|-----------------|---------|
| Text PDF | 1 MB | ~2s | ~50 |
| Scanned PDF (OCR) | 1 MB | ~15s | ~50 |
| DOCX | 500 KB | ~1s | ~25 |
| CSV | 2 MB | ~3s | ~100 |

### Optimization Tips

1. **Batch uploads**: Upload multiple files in one request
2. **Adjust chunk size**: Modify in `utils/document_processor.py`
3. **Disable OCR**: For text-only PDFs, set `enable_ocr=false`
4. **Use background tasks**: Large files process asynchronously

## Security

- ✅ API key authentication required
- ✅ File size limits (50MB default)
- ✅ File type validation
- ✅ Soft deletion (audit trail)
- ⚠️ Consider adding: Virus scanning, content filtering

## Future Enhancements

- [ ] Support for more file types (.ppt, .xls, .html)
- [ ] Document versioning
- [ ] Duplicate detection
- [ ] Batch processing API
- [ ] Real-time progress updates (WebSocket)
- [ ] Content-based access control
- [ ] Advanced search filters

## Support

For issues or questions:
- Review logs in `app.log`
- Check LangSmith traces
- Verify database migrations
- Ensure all dependencies are installed

---

**Last Updated**: January 10, 2025  
**Version**: 1.0.0
