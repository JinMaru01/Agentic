from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Multi-Agent Access Management")

app.include_router(router)