from fastapi import FastAPI
from app.api.api_routes import (chat_agent, 
                                knowledge_base, 
                                delete_pdf,
                                conversation_category,
                                conversation_end_check)

app = FastAPI(title="eeV-AI Bot API")

app.include_router(chat_agent.router)
app.include_router(knowledge_base.router)
app.include_router(delete_pdf.router)
app.include_router(conversation_category.router)
app.include_router(conversation_end_check.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the eeV-AI Bot API"}

## To run the app, use the command:
## uvicorn app.main:app --reload