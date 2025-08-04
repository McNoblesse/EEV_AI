from fastapi import FastAPI
from route import tier_3_model, voice_ai_route, freshdesk
from config.database import engine, Base
from model import database_models, freshdesk_model



print("Initializing database and creating tables if they don't exist...")
Base.metadata.create_all(bind=engine)
print("Database initialization complete.")

app = FastAPI(root_path="/eeVai")

app.include_router(router=tier_3_model.router)
app.include_router(router=voice_ai_route.router)
app.include_router(router=freshdesk.router)

