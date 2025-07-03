from fastapi import FastAPI
from route import tier_1_model

app = FastAPI(root_path="/eeVai")

app.include_router(router=tier_1_model.router)

