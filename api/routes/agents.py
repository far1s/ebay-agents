"""
/api/agents — start/stop/status endpoints and run history.
"""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from tools.supabase_client import SupabaseClient

router = APIRouter()
logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

# Track the currently running task
_active_run_id: str | None = None


class RunRequest(BaseModel):
    run_id: str | None = None


def _run_crew(run_id: str | None = None):
    global _active_run_id
    try:
        from crew.main_crew import EbayAgentsCrew
    except ImportError:
        _active_run_id = None
        raise RuntimeError(
            "CrewAI is not installed in this environment. "
            "Run the pipeline locally: python -c \"from crew.main_crew import EbayAgentsCrew; EbayAgentsCrew().run()\""
        )
    crew = EbayAgentsCrew()
    result = crew.run(run_id)
    _active_run_id = None
    return result


@router.post("/run")
async def trigger_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Trigger a full pipeline run in the background."""
    global _active_run_id
    if _active_run_id:
        raise HTTPException(status_code=409, detail=f"A run is already in progress: {_active_run_id}")

    import uuid
    from datetime import datetime, timezone

    run_id = request.run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    _active_run_id = run_id

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_crew, run_id)

    return {"run_id": run_id, "status": "started", "message": "Pipeline started in background"}


@router.get("/status")
async def get_status():
    """Get current system status and active run info."""
    try:
        db = SupabaseClient()
        runs = db.get_runs(limit=1)
        latest_run = runs[0] if runs else None

        performance = {}
        agent_names = ["market_agent", "design_agent", "telegram_agent", "listing_agent", "boss_agent"]
        for name in agent_names:
            scores = db.get_performance(agent_name=name, limit=5)
            avg = sum(s["score"] for s in scores) / len(scores) if scores else 0
            performance[name] = {
                "last_score": scores[0]["score"] if scores else None,
                "avg_score": round(avg, 1),
                "last_run": scores[0]["timestamp"] if scores else None,
                "status": "running" if _active_run_id else "idle",
            }

        pending_approvals = db.get_pending_approvals()

        return {
            "system_status": "running" if _active_run_id else "idle",
            "active_run_id": _active_run_id,
            "latest_run": latest_run,
            "agents": performance,
            "pending_approvals": len(pending_approvals),
        }
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/runs")
async def get_runs(limit: Annotated[int, Query(ge=1, le=100)] = 20):
    """List all pipeline runs."""
    db = SupabaseClient()
    return {"runs": db.get_runs(limit=limit)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get details for a specific run."""
    db = SupabaseClient()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    performance = db.get_performance(limit=100)
    run_performance = [p for p in performance if p.get("run_id") == run_id]
    market = db.get_market_research(run_id)
    products = db.get_generated_products(run_id)
    logs = db.get_logs(run_id=run_id, limit=50)

    return {
        "run": run,
        "agent_performance": run_performance,
        "market_research": market,
        "generated_products": products,
        "recent_logs": logs,
    }
