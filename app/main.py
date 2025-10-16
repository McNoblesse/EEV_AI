from fastapi import FastAPI
from api.api_routes import chat_agent, knowledge_base

app = FastAPI(title="eeV-AI Bot API")

app.include_router(chat_agent.router)
app.include_router(knowledge_base.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the eeV-AI Bot API"}