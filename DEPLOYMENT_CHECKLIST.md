# 🚀 Document Ingestion System - Deployment Checklist

## Pre-Deployment Steps

### 1. Install Python Dependencies ✅
```bash
pip install -r requirements.txt
```

**New packages added**:
- PyPDF2==3.0.1
- python-docx==1.1.2
- pdf2image==1.17.0
- pytesseract==0.3.13

---

### 2. Install System Dependencies ⚙️

#### Windows
```bash
# Download and install Tesseract OCR
# URL: https://github.com/UB-Mannheim/tesseract/wiki
# Install to: C:\Program Files\Tesseract-OCR
# Add to PATH environment variable

# Download Poppler (for pdf2image)
# URL: https://github.com/oschwartz10612/poppler-windows/releases/
# Extract and add bin folder to PATH
```

#### Linux
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install poppler-utils
```

#### macOS
```bash
brew install tesseract
brew install poppler
```

---

### 3. Configure Environment Variables 🔐

Add to `.env` file:

```bash
# Existing (Verify these are set)
PINECONE_API_KEY=your_pinecone_key
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
POSTGRES_MEMORY_URL=postgresql://user:pass@host:port/dbname
TIER1_API_KEY=your_tier1_key
TIER2_API_KEY=your_tier2_key
TIER3_API_KEY=your_tier3_key
JWT_SECRET_KEY=your_jwt_secret
JWT_ALGORITHM=HS256

# NEW - LangSmith Monitoring (Optional but Recommended)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=eev-ai-production
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**To get LangSmith API key**:
1. Visit: https://smith.langchain.com
2. Sign up/Login
3. Go to Settings → API Keys
4. Create new key

---

### 4. Run Database Migration 🗄️

**Option 1: Direct table creation** (Recommended)
```bash
python -c "from config.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

**Option 2: Manual SQL execution**
```sql
-- Connect to your PostgreSQL database and run:
-- See: alembic/versions/001_document_uploads.py for full SQL
```

**Verify migration**:
```bash
python setup_verification.py
```

---

### 5. Verify Installation ✅

Run the verification script:
```bash
python setup_verification.py
```

**Expected output**:
```
✅ PASS - Python Version
✅ PASS - Dependencies
✅ PASS - Tesseract OCR
✅ PASS - Environment Config
✅ PASS - Database Connection
✅ PASS - Database Tables
```

---

## Deployment Steps

### 1. Start the Server 🚀

**Development mode**:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode**:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**With Gunicorn (Production)**:
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

### 2. Test the API 🧪

#### A. Health Check
```bash
curl http://localhost:8000/
```

**Expected response**:
```json
{
  "message": "EEV AI Assistant API is running",
  "version": "2.0.0",
  "status": "healthy",
  "features": [...]
}
```

#### B. Test Document Upload
```bash
# Create a test file
echo "This is a test document for knowledge base testing." > test.txt

# Upload the file
curl -X POST "http://localhost:8000/api/v1/knowledge-base/upload" \
  -H "Authorization: Bearer YOUR_TIER1_API_KEY" \
  -F "files=@test.txt" \
  -F "category=Test" \
  -F "enable_ocr=true"
```

**Expected response**:
```json
{
  "uploaded_documents": [
    {
      "id": 1,
      "filename": "test.txt",
      "status": "processing",
      "message": "Document uploaded and queued for processing"
    }
  ],
  "total_files": 1,
  "successful": 1,
  "failed": 0
}
```

#### C. Check Processing Status
```bash
# Wait a few seconds for processing, then:
curl -X GET "http://localhost:8000/api/v1/knowledge-base/documents" \
  -H "Authorization: Bearer YOUR_TIER1_API_KEY"
```

**Expected**: Status should be "indexed"

#### D. View Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/knowledge-base/stats" \
  -H "Authorization: Bearer YOUR_TIER1_API_KEY"
```

---

### 3. Test OCR Functionality (Optional) 📄

If you have scanned PDFs, test OCR:

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge-base/upload" \
  -H "Authorization: Bearer YOUR_TIER1_API_KEY" \
  -F "files=@scanned_document.pdf" \
  -F "category=Scanned Documents" \
  -F "enable_ocr=true"
```

Check logs for OCR processing messages.

---

### 4. Monitor with LangSmith 📊

If LangSmith is configured:

1. Visit: https://smith.langchain.com
2. Select your project: "eev-ai-production"
3. View traces for:
   - Document processing
   - Embedding generation
   - Vector store operations

---

## Post-Deployment Verification

### ✅ Checklist

- [ ] Server starts without errors
- [ ] Health check endpoint responds
- [ ] Upload endpoint accepts files
- [ ] Documents are processed successfully
- [ ] Chunks are created and counted
- [ ] Vectors are stored in Pinecone
- [ ] Database records are updated
- [ ] List endpoint returns documents
- [ ] Stats endpoint shows metrics
- [ ] Delete endpoint removes documents
- [ ] Logs are being written to app.log
- [ ] LangSmith traces appear (if enabled)

---

## Monitoring & Maintenance

### Daily Checks

1. **Check logs**:
   ```bash
   tail -f app.log
   ```

2. **Monitor failed uploads**:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/knowledge-base/documents?status=failed" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

3. **Review statistics**:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/knowledge-base/stats" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

### Weekly Maintenance

1. **Clean up old temporary files** (if any)
2. **Review Pinecone usage and costs**
3. **Check database size growth**
4. **Review LangSmith traces for errors**

---

## Troubleshooting

### Issue: "Tesseract not found"

**Solution**:
1. Install Tesseract (see step 2 above)
2. Add to PATH
3. Restart terminal/server

**Verify**:
```bash
tesseract --version
```

---

### Issue: "pdf2image requires poppler"

**Solution**:
1. Install poppler (see step 2 above)
2. Add to PATH (Windows)
3. Restart terminal/server

---

### Issue: "Table document_uploads does not exist"

**Solution**:
```bash
python -c "from config.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

---

### Issue: "Background processing not working"

**Check**:
1. Database connection is stable
2. Pinecone API key is valid
3. Check app.log for errors
4. Verify Gemini API key for embeddings

---

### Issue: "Out of memory during processing"

**Solution**:
1. Reduce chunk_size in `utils/document_processor.py`
2. Process fewer files at once
3. Increase server memory allocation

---

## API Documentation

Once deployed, access interactive API docs at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Support Resources

### Documentation
- `KNOWLEDGE_BASE_DOCS.md` - Complete API documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `README.md` - Project overview

### Logs
- `app.log` - Application logs
- Console output - Real-time processing logs

### Monitoring
- LangSmith: https://smith.langchain.com
- Pinecone Console: https://app.pinecone.io

---

## Rollback Plan

If issues occur:

1. **Stop the server**:
   ```bash
   # Kill the uvicorn process
   ```

2. **Rollback database** (if needed):
   ```sql
   DROP TABLE IF EXISTS document_uploads;
   ```

3. **Remove router registration** from `main.py`:
   ```python
   # Comment out:
   # app.include_router(knowledge_base_router)
   ```

4. **Restart server**:
   ```bash
   uvicorn main:app --reload
   ```

---

## Performance Optimization

### For High Volume

1. **Increase workers**:
   ```bash
   uvicorn main:app --workers 8
   ```

2. **Use Redis for background tasks** (instead of BackgroundTasks)

3. **Batch processing**:
   - Process multiple documents in parallel
   - Use queue system (Celery/RQ)

4. **Database optimization**:
   - Add more indexes
   - Use connection pooling
   - Regular VACUUM operations

---

## Security Checklist

- [ ] API key authentication enabled
- [ ] File size limits enforced (50MB default)
- [ ] File type validation active
- [ ] SQL injection protection (using ORM)
- [ ] CORS configured properly
- [ ] HTTPS enabled (production)
- [ ] Rate limiting implemented (optional)
- [ ] Virus scanning considered (optional)

---

## Success Criteria

### ✅ System is ready when:

1. All verification checks pass
2. Test upload completes successfully
3. Documents appear in database
4. Vectors stored in Pinecone
5. API endpoints respond correctly
6. Logs show no errors
7. LangSmith traces visible (if enabled)

---

## Contact & Support

For issues or questions:
- Check `app.log` for error messages
- Review LangSmith traces
- Consult `KNOWLEDGE_BASE_DOCS.md`
- Check database connection and migrations

---

**Last Updated**: January 10, 2025  
**Version**: 1.0.0  
**Status**: ✅ READY FOR DEPLOYMENT
