"""
FastAPI entry point for EbayAgents backend.

Deployed on Vercel as a Python serverless function under /api/*.
Also runnable locally: uvicorn api.main:app --reload --port 8000
"""
import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Capture any import errors from route modules so the app still starts
_import_errors: dict[str, str] = {}

try:
    from api.routes import agents
except Exception as exc:
    _import_errors["agents"] = traceback.format_exc()
    agents = None  # type: ignore

try:
    from api.routes import listings
except Exception as exc:
    _import_errors["listings"] = traceback.format_exc()
    listings = None  # type: ignore

try:
    from api.routes import logs
except Exception as exc:
    _import_errors["logs"] = traceback.format_exc()
    logs = None  # type: ignore

try:
    from api.routes import schedule
except Exception as exc:
    _import_errors["schedule"] = traceback.format_exc()
    schedule = None  # type: ignore

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

if agents:
    app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
if listings:
    app.include_router(listings.router, prefix="/api/listings", tags=["Listings"])
if logs:
    app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
if schedule:
    app.include_router(schedule.router, prefix="/api/schedule", tags=["Schedule"])


@app.get("/api/health")
async def health():
    """Quick health check — also verifies API key presence and import status."""
    checks = {
        "api": "ok",
        "python": sys.version,
        "anthropic": "ok" if os.getenv("ANTHROPIC_API_KEY") else "missing key",
        "ebay": "ok" if os.getenv("EBAY_APP_ID") else "missing key",
        "telegram": "ok" if os.getenv("TELEGRAM_BOT_TOKEN") else "missing key",
        "supabase": "ok" if os.getenv("SUPABASE_URL") else "missing key",
        "supabase_key": "ok" if os.getenv("SUPABASE_SERVICE_ROLE_KEY") else "missing key",
        "ebay_sandbox": os.getenv("EBAY_SANDBOX_MODE", "true"),
        "import_errors": _import_errors if _import_errors else None,
    }
    return checks


@app.get("/")
async def root():
    return {"message": "EbayAgents API", "docs": "/docs"}
