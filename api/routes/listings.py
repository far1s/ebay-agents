"""
/api/listings — Etsy listing data.
"""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from tools.supabase_client import SupabaseClient

router = APIRouter()


@router.get("")
async def get_listings(
    status: Annotated[str | None, Query(description="Filter by status: active, sold, ended")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Return all Etsy listings with optional status filter."""
    db = SupabaseClient()
    listings = db.get_listings(status=status, limit=limit)

    total = len(listings)
    active = sum(1 for l in listings if l.get("status") == "active")
    sold = sum(1 for l in listings if l.get("status") == "sold")

    return {
        "listings": listings,
        "total": total,
        "stats": {"active": active, "sold": sold, "ended": total - active - sold},
    }


@router.get("/{listing_id}")
async def get_listing(listing_id: str):
    """Get a single listing by its UUID."""
    db = SupabaseClient()
    rows = db.client.table("listings").select("*").eq("id", listing_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Listing not found")
    return rows[0]
