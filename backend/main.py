"""Standalone demo server. In the team app, copy only the two marked lines.

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whatsapp_alerts import alerts_lifespan, alerts_router
from whatsapp_alerts.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="WhatsApp family alerts", lifespan=alerts_lifespan)  # <- 1
app.include_router(alerts_router)  # <- 2

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}
