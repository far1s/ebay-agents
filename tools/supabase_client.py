import os
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


class SupabaseClient:
    def __init__(self) -> None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.client: Client = create_client(url, key)

    # ── Agent Runs ────────────────────────────────────────────────────────────

    def create_run(self, run_id: str) -> dict:
        data = {"run_id": run_id, "status": "running", "started_at": _now()}
        return self.client.table("agent_runs").insert(data).execute().data[0]

    def update_run(self, run_id: str, status: str, boss_report: dict | None = None) -> None:
        payload: dict[str, Any] = {"status": status, "completed_at": _now()}
        if boss_report:
            payload["boss_report"] = boss_report
        self.client.table("agent_runs").update(payload).eq("run_id", run_id).execute()

    def get_runs(self, limit: int = 20) -> list[dict]:
        return (
            self.client.table("agent_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    def get_run(self, run_id: str) -> dict | None:
        rows = self.client.table("agent_runs").select("*").eq("run_id", run_id).execute().data
        return rows[0] if rows else None

    # ── Agent Performance ─────────────────────────────────────────────────────

    def save_performance(self, run_id: str, agent_name: str, score: int, notes: str = "") -> None:
        data = {
            "run_id": run_id,
            "agent_name": agent_name,
            "score": max(1, min(10, score)),
            "notes": notes,
            "timestamp": _now(),
        }
        self.client.table("agent_performance").insert(data).execute()

    def get_performance(self, agent_name: str | None = None, limit: int = 50) -> list[dict]:
        q = self.client.table("agent_performance").select("*").order("timestamp", desc=True).limit(limit)
        if agent_name:
            q = q.eq("agent_name", agent_name)
        return q.execute().data

    # ── Market Research ───────────────────────────────────────────────────────

    def save_market_research(
        self,
        run_id: str,
        product_type: str,
        keywords: list[str],
        avg_price: float,
        sales_volume: int,
        opportunity_score: float,
        raw_data: dict,
    ) -> dict:
        data = {
            "run_id": run_id,
            "product_type": product_type,
            "keywords": keywords,
            "avg_price": avg_price,
            "sales_volume": sales_volume,
            "opportunity_score": opportunity_score,
            "raw_data": raw_data,
        }
        return self.client.table("market_research").insert(data).execute().data[0]

    def get_market_research(self, run_id: str) -> list[dict]:
        return (
            self.client.table("market_research")
            .select("*")
            .eq("run_id", run_id)
            .order("opportunity_score", desc=True)
            .execute()
            .data
        )

    # ── Generated Products ────────────────────────────────────────────────────

    def save_generated_product(
        self,
        run_id: str,
        product_type: str,
        file_path: str,
        preview_path: str,
        design_score: int,
        metadata: dict,
    ) -> dict:
        data = {
            "run_id": run_id,
            "product_type": product_type,
            "file_path": file_path,
            "preview_path": preview_path,
            "design_score": design_score,
            "metadata": metadata,
        }
        return self.client.table("generated_products").insert(data).execute().data[0]

    def get_generated_products(self, run_id: str) -> list[dict]:
        return (
            self.client.table("generated_products")
            .select("*")
            .eq("run_id", run_id)
            .execute()
            .data
        )

    # ── Approval Log ──────────────────────────────────────────────────────────

    def create_approval(
        self,
        run_id: str,
        product_id: str,
        suggested_price: float,
        telegram_message_id: int | None = None,
    ) -> dict:
        data = {
            "run_id": run_id,
            "product_id": product_id,
            "suggested_price": suggested_price,
            "status": "pending",
            "telegram_message_id": telegram_message_id,
        }
        return self.client.table("approval_log").insert(data).execute().data[0]

    def update_approval(
        self,
        approval_id: str,
        status: str,
        final_price: float | None = None,
    ) -> None:
        payload: dict[str, Any] = {"status": status, "decided_at": _now()}
        if final_price is not None:
            payload["final_price"] = final_price
        self.client.table("approval_log").update(payload).eq("id", approval_id).execute()

    def get_pending_approvals(self) -> list[dict]:
        return (
            self.client.table("approval_log")
            .select("*")
            .eq("status", "pending")
            .execute()
            .data
        )

    # ── Listings ──────────────────────────────────────────────────────────────

    def save_listing(
        self,
        run_id: str,
        product_id: str,
        ebay_listing_id: str,
        ebay_url: str,
        title: str,
        price: float,
    ) -> dict:
        data = {
            "run_id": run_id,
            "product_id": product_id,
            "ebay_listing_id": ebay_listing_id,
            "ebay_url": ebay_url,
            "title": title,
            "price": price,
            "status": "active",
            "listed_at": _now(),
        }
        return self.client.table("listings").insert(data).execute().data[0]

    def get_listings(self, status: str | None = None, limit: int = 50) -> list[dict]:
        q = self.client.table("listings").select("*").order("listed_at", desc=True).limit(limit)
        if status:
            q = q.eq("status", status)
        return q.execute().data

    # ── Agent Logs ────────────────────────────────────────────────────────────

    def log(
        self,
        agent_name: str,
        message: str,
        level: str = "info",
        run_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "agent_name": agent_name,
            "level": level,
            "message": message,
            "timestamp": _now(),
        }
        if run_id:
            data["run_id"] = run_id
        if metadata:
            data["metadata"] = metadata
        self.client.table("agent_logs").insert(data).execute()

    def get_logs(
        self,
        run_id: str | None = None,
        agent_name: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        q = (
            self.client.table("agent_logs")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
        )
        if run_id:
            q = q.eq("run_id", run_id)
        if agent_name:
            q = q.eq("agent_name", agent_name)
        if level:
            q = q.eq("level", level)
        return q.execute().data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
