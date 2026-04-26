"""
/api/logs — agent log stream with filtering.
"""
from typing import Annotated

from fastapi import APIRouter, Query

from tools.supabase_client import SupabaseClient

router = APIRouter()


@router.get("")
async def get_logs(
    run_id: Annotated[str | None, Query()] = None,
    agent_name: Annotated[str | None, Query()] = None,
    level: Annotated[str | None, Query(description="info, warning, error, debug")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Stream agent logs with optional filters."""
    db = SupabaseClient()
    logs = db.get_logs(run_id=run_id, agent_name=agent_name, level=level, limit=limit)
    return {"logs": logs, "count": len(logs)}
