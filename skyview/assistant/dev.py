"""Local assistant server without startup migrations against the farm database.

Run: uvicorn skyview.assistant.dev:app --port 8001
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skyview.api.assistant_routes import router

app = FastAPI(title="Kisan Mitra local assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
