from fastapi import FastAPI

from app.api.routes_chat import router as chat_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_health import router as health_router
from app.api.routes_admin import router as admin_router
from app.storage.db import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title='SAN RAG Web Bot')
app.include_router(chat_router)
app.include_router(feedback_router)
app.include_router(health_router)
app.include_router(admin_router)
