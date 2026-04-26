"""
FastAPI entry point for EbayAgents backend.

Deployed on Vercel as a Python serverless function under /api/*.
Also runnable locally: uvicorn api.main:app --reload --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import agents, listings, logs, schedule

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("EbayAgents API starting up")
    yield
    logging.getLogger(__name__).info("EbayAgents API shutting down")


app = FastAPI(
    title="EbayAgents API",
    description="Backend API for the EbayAgents automated eBay digital product sales system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(listings.router, prefix="/api/listings", tags=["Listings"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["Schedule"])


@app.get("/api/health")
async def health():
    """Quick health check — also verifies API key presence."""
    checks = {
        "api": "ok",
        "anthropic": "ok" if os.getenv("ANTHROPIC_API_KEY") else "missing key",
        "ebay": "ok" if os.getenv("EBAY_APP_ID") else "missing key",
        "telegram": "ok" if os.getenv("TELEGRAM_BOT_TOKEN") else "missing key",
        "supabase": "ok" if os.getenv("SUPABASE_URL") else "missing key",
        "ebay_sandbox": os.getenv("EBAY_SANDBOX_MODE", "true"),
    }
    return checks


@app.get("/")
async def root():
    return {"message": "EbayAgents API", "docs": "/docs"}
