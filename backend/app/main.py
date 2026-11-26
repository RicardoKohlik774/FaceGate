"""Creates the FastAPI app and registers the routers.

Run from the backend/ folder:

    python -m uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs to see and try every endpoint.
"""
from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="FaceGate API")

# Every endpoint lives under /api, so the web app can be served from the same
# address later without clashing with the API.
app.include_router(health.router, prefix="/api")
