# COMPLETE IMPLEMENTATION GUIDE - EEV AI Enhancements

## 🎯 Current Status

### ✅ Completed
1. **Document Ingestion System** - FULLY IMPLEMENTED
   - Multi-format support (PDF with OCR, CSV, TXT, DOCX)
   - Pinecone integration with auto-embedding
   - 6 API endpoints for document management
   - Background async processing

2. **Database Schema Refactoring** - CODE READY
   - `Conversation` table simplified (12 columns)
   - `ConversationAnalytics` table created (analytics data)
   - `VoiceMetadata` table created (voice-specific data)
   - Migration file created: `002_split_conversation_tables.py`

3. **LangSmith Monitoring** - CONFIGURED
   - Environment variables added to `config/access_keys.py`
   - Initialization added to `main.py`

### 🔄 Ready to Implement (Files Created)
The following files are ready but not yet integrated into `main.py`:

1. **Query Complexity Module** - `utils/complexity_analyzer.py`
2. **Tier 1 Endpoint** - `route/tier_1_model.py`
3. **Tier 2 Endpoint** - `route/tier_2_model.py`
4. **WhatsApp Integration** - `route/whatsapp.py`

---

## 📋 DEPLOYMENT STEPS (In Order)

### Step 1: Run Database Migration ✅

```bash
# Backup first (IMPORTANT!)
# If using PostgreSQL:
# pg_dump your_database > backup_before_migration_$(date +%Y%m%d).sql

# Run migration
python -c "from alembic import command; from alembic.config import Config; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"

# Verify new tables created
python -c "from sqlalchemy import inspect; from config.database import engine; print('Tables:', inspect(engine).get_table_names())"
```

**Expected output:**
```
Tables: ['conversations', 'conversation_analytics', 'voice_metadata', 'agent_sessions', 
         'knowledge_base_usage', 'escalation_logs', 'document_uploads', ...]
```

---

### Step 2: Install Missing Dependencies

```bash
# Install document processing libraries (already in requirements.txt)
pip install PyPDF2==3.0.1 python-docx==1.1.2 pdf2image==1.17.0 pytesseract==0.3.13

# Install Tesseract OCR system dependency
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt-get install tesseract-ocr poppler-utils
# macOS: brew install tesseract poppler
```

---

### Step 3: Update Environment Variables

Add to `.env` file:

```bash
# === EXISTING (Verify these are set) ===
PINECONE_API_KEY=your_key
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
POSTGRES_MEMORY_URL=postgresql://...
TIER1_API_KEY=your_key
TIER2_API_KEY=your_key
TIER3_API_KEY=your_key

# === NEW - LangSmith Monitoring ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=eev-ai-production
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# === NEW - WhatsApp Business API ===
WHATSAPP_API_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=eev_ai_verify_2025

# === FUTURE - Social Media (Optional) ===
FACEBOOK_PAGE_ACCESS_TOKEN=
INSTAGRAM_ACCESS_TOKEN=
```

---

### Step 4: Update `config/access_keys.py`

```bash
# Already updated in your file, but verify these fields exist:
```

```python
class AccessKeys(BaseSettings):
    # ... existing fields ...
    
    # LangSmith (Already added)
    LANGCHAIN_TRACING_V2: Optional[str] = "false"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = "eev-ai-production"
    
    # WhatsApp (ADD THESE)
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "eev_ai_verify_2025"
    
    # Social Media (Future)
    FACEBOOK_PAGE_ACCESS_TOKEN: Optional[str] = ""
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = ""
```

---

### Step 5: Register New Routers in `main.py`

```python
# ADD these imports at the top
from route.tier_1_model import router as tier1_router
from route.tier_2_model import router as tier2_router
from route.whatsapp import router as whatsapp_router

# ADD these router registrations (after existing routers)
app.include_router(tier1_router, prefix="/api/v1")
app.include_router(tier2_router, prefix="/api/v1")
app.include_router(whatsapp_router, prefix="/api/v1")
```

Full router registration section should look like:

```python
# Include routers
app.include_router(voice_router, prefix="/api/v1")
app.include_router(tier1_router, prefix="/api/v1")  # NEW
app.include_router(tier2_router, prefix="/api/v1")  # NEW
app.include_router(tier3_router, prefix="/api/v1")
app.include_router(freshdesk_router, prefix="/api/v1")
app.include_router(knowledge_base_router)  # Already has prefix
app.include_router(whatsapp_router, prefix="/api/v1")  # NEW
```

---

### Step 6: Update Document Upload Limits in `route/knowledge_base.py`

Find the `upload_documents` function and update:

```python
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
    
    # === ADD THIS VALIDATION ===
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
    # === END VALIDATION ===
    
    # ... rest of existing code ...
```

---

### Step 7: Update Tier 3 to Save to Split Tables

In `route/tier_3_model.py`, find where conversation is saved to DB and update:

```python
# REPLACE THIS SECTION (around line 120-150):

# OLD CODE (single table save):
# new_conversation = Conversation(
#     session_id=data.session_id,
#     user_query=data.user_query,
#     bot_response=final_response,
#     entities=[entity.dict() for entity in analysis_result.entities],
#     reasoning_steps=final_agent_state.get("reasoning_steps", []),
#     ...
# )

# NEW CODE (split table saves):
from model.database_models import Conversation, ConversationAnalytics, VoiceMetadata

# 1. Save core conversation data
new_conversation = Conversation(
    session_id=data.session_id,
    user_query=data.user_query,
    bot_response=final_response,
    intent=analysis_result.intent.value if hasattr(analysis_result.intent, 'value') else str(analysis_result.intent),
    intent_confidence=analysis_result.intent_confidence,
    sentiment=analysis_result.sentiment,
    complexity_score=analysis_result.complexity_score,
    channel=getattr(data, 'channel', 'chat'),
    requires_escalation=analysis_result.requires_human_escalation
)
db.add(new_conversation)
db.commit()
db.refresh(new_conversation)

# 2. Save analytics data (separate table)
analytics = ConversationAnalytics(
    conversation_id=new_conversation.id,
    entities=[entity.dict() for entity in analysis_result.entities],
    keywords=analysis_result.keywords,
    complexity_factors=analysis_result.complexity_factors,
    reasoning_steps=final_agent_state.get("reasoning_steps", []),
    tool_calls_used=final_agent_state.get("current_tool_calls", []),
    retrieval_context=final_agent_state.get("retrieved_context", []),
    processing_time_ms=int(processing_time_ms),
    tokens_used=final_agent_state.get("tokens_used", 0),
    model_used="gpt-4o-mini"
)
db.add(analytics)
db.commit()

# 3. If voice channel, save voice metadata
if getattr(data, 'channel', 'chat') == 'voice':
    voice_meta = VoiceMetadata(
        conversation_id=new_conversation.id,
        transcription_model="whisper-1",
        tts_model="tts-1",
        voice_used="alloy",
        audio_file_path=getattr(data, 'audio_path', None)
    )
    db.add(voice_meta)
    db.commit()
```

---

## 🧪 TESTING CHECKLIST

### 1. Test Database Migration

```bash
# Check tables exist
python -c "from sqlalchemy import inspect; from config.database import engine; print(inspect(engine).get_table_names())"

# Should show: conversation_analytics, voice_metadata
```

### 2. Test Tier 1 Endpoint

```bash
curl -X POST "http://localhost:8000/api/v1/model/tier_1_model" \
  -H "tier_1_key_auth: YOUR_TIER1_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "Hello! How are you?",
    "session_id": "test_session_1",
    "channel": "chat"
  }'

# Expected: Quick greeting response with complexity_score < 30
```

### 3. Test Tier 2 Endpoint

```bash
curl -X POST "http://localhost:8000/api/v1/model/tier_2_model" \
  -H "tier_1_key_auth: YOUR_TIER1_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "How do I integrate your API with my Node.js application?",
    "session_id": "test_session_2",
    "channel": "chat"
  }'

# Expected: Detailed response with complexity_score 31-70
```

### 4. Test Document Upload Limits

```bash
# Test: Upload 6 files (should fail)
# Test: Upload 5 files > 200MB total (should fail)
# Test: Upload 5 files < 200MB total (should succeed)
```

### 5. Test WhatsApp Webhook Verification

```bash
curl "http://localhost:8000/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=eev_ai_verify_2025&hub.challenge=12345"

# Expected response: 12345
```

### 6. Test LangSmith Monitoring

1. Set `LANGCHAIN_TRACING_V2=true` in `.env`
2. Make any API call (tier1, tier2, tier3)
3. Visit https://smith.langchain.com
4. Check for traces in your project

---

## 📊 ARCHITECTURE OVERVIEW

### Multi-Tier Routing System

```
User Query
    │
    ▼
┌─────────────────────────┐
│ Complexity Analyzer     │
│ (Fast Rule-Based)       │
└─────────┬───────────────┘
          │
          ├─── Score 0-30 ──────▶ Tier 1 (Greetings, Simple FAQs)
          │                       • Fast path (< 50ms)
          │                       • Greeting tool
          │                       • Basic retrieval
          │
          ├─── Score 31-60 ─────▶ Tier 2 (Moderate Complexity)
          │                       • Knowledge base search
          │                       • LLM analysis
          │                       • Can escalate to human
          │
          └─── Score 61-100 ────▶ Tier 3 (Full Copilot)
                                  • Multi-step reasoning
                                  • LangGraph workflow
                                  • PostgreSQL checkpointer
```

### Database Schema (Refactored)

```
conversations (Core - 12 columns)
├── id, session_id, user_query, bot_response
├── intent, sentiment, complexity_score
├── channel, requires_escalation
└── timestamp, created_at

conversation_analytics (Debug Data)
├── conversation_id (FK)
├── entities, keywords, complexity_factors
├── reasoning_steps, tool_calls_used
└── processing_time_ms, tokens_used, model_used

voice_metadata (Voice-Specific)
├── conversation_id (FK)
├── transcription_model, tts_model, voice_used
└── audio_file_path, audio_duration, confidence
```

---

## 🚀 POST-DEPLOYMENT

### 1. Configure WhatsApp Webhook

In Meta Business Suite:
1. Go to WhatsApp > Configuration > Webhooks
2. Set callback URL: `https://your-domain.com/api/v1/whatsapp/webhook`
3. Set verify token: `eev_ai_verify_2025`
4. Subscribe to: `messages`

### 2. Monitor System

- **Logs**: `tail -f app.log`
- **LangSmith**: https://smith.langchain.com
- **Database**: Check conversation splits are working

### 3. Performance Tuning

```python
# Adjust complexity thresholds in utils/complexity_analyzer.py
# Tune chunk sizes in utils/document_processor.py
# Monitor Pinecone usage and costs
```

---

## 🎯 SUCCESS CRITERIA

✅ All migrations run without errors
✅ New tables visible in database
✅ Tier 1 endpoint responds quickly (< 100ms)
✅ Tier 2 endpoint provides detailed responses
✅ Tier 3 saves to split tables
✅ Document upload enforces 5-file, 200MB limits
✅ WhatsApp webhook verification succeeds
✅ LangSmith traces appear for all requests

---

## 🔜 FUTURE ENHANCEMENTS

### Phase 2 (Next Sprint)
- [ ] Facebook/Instagram Messenger integration
- [ ] Unified channel router/adapter pattern
- [ ] Advanced media processing (image OCR, voice transcription)
- [ ] Real-time progress updates (WebSocket)

### Phase 3 (Long-term)
- [ ] Zendesk & Zoho Desk integration
- [ ] A/B testing framework for agent responses
- [ ] Advanced analytics dashboard
- [ ] Auto-categorization with AI
- [ ] Document versioning system

---

## 📞 SUPPORT & TROUBLESHOOTING

### Common Issues

**Issue**: "relationship is not defined"
**Solution**: Check imports at top of `database_models.py`

**Issue**: "Table conversations has no column X"
**Solution**: Run migration: `alembic upgrade head`

**Issue**: "WhatsApp webhook verification failed"
**Solution**: Check `WHATSAPP_VERIFY_TOKEN` matches Meta configuration

**Issue**: "Tesseract not found"
**Solution**: Install Tesseract OCR and add to PATH

---

## 📄 FILES OVERVIEW

### Created Files
- `utils/complexity_analyzer.py` - Query complexity module
- `route/tier_1_model.py` - Simple query handler
- `route/tier_2_model.py` - Moderate complexity handler
- `route/whatsapp.py` - WhatsApp Business API integration
- `alembic/versions/002_split_conversation_tables.py` - Database migration

### Modified Files
- `model/database_models.py` - Split schema (3 tables instead of 1)
- `config/access_keys.py` - Added WhatsApp & LangSmith config
- `main.py` - LangSmith initialization (already done)
- `route/knowledge_base.py` - Need to add 5-file/200MB limits
- `route/tier_3_model.py` - Need to update DB save logic

---

**Last Updated**: January 10, 2025
**Status**: ✅ READY FOR DEPLOYMENT (pending steps 5-7)
**Version**: 2.0.0
