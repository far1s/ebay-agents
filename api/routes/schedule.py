"""
/api/schedule — cron settings and the Vercel cron trigger endpoint.
"""
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).parent.parent.parent / "schedule_settings.json"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {"enabled": True, "cron": "0 9 * * *", "timezone": "UTC"}


def _save_settings(data: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class ScheduleSettings(BaseModel):
    enabled: bool
    cron: str
    timezone: str = "UTC"


@router.get("")
async def get_schedule():
    """Return current schedule settings."""
    return _load_settings()


@router.post("")
async def update_schedule(settings: ScheduleSettings):
    """Update schedule settings."""
    data = settings.model_dump()
    _save_settings(data)
    return {"saved": True, "settings": data}


@router.post("/run")
async def cron_trigger(request: Request):
    """
    Vercel Cron endpoint — called daily at 9:00 AM UTC.
    Also callable manually to trigger a run.
    """
    settings = _load_settings()
    if not settings.get("enabled", True):
        return {"status": "skipped", "reason": "Schedule is disabled"}

    try:
        from crew.main_crew import EbayAgentsCrew
    except ImportError:
        return {
            "status": "unavailable",
            "message": "CrewAI not installed in this deployment. Trigger runs locally or on a full server.",
        }

    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()
    crew = EbayAgentsCrew()
    loop.run_in_executor(executor, crew.run)

    return {"status": "started", "message": "Cron run triggered"}
