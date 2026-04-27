"""
EtsyAgentsCrew — the central CrewAI orchestration.

Pipeline:
  1. Market Agent  → research Etsy for best-selling digital product
  2. Design Agent  → generate 3 PDF variations, pick the best
  3. Telegram Agent → send approval request; wait for owner response
  4. Listing Agent → create live Etsy listing (only if approved)
  5. Boss Agent    → score all agents, save final report

The Boss Agent runs as a hierarchical manager who can reassign
failed tasks and inject corrected instructions.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from crewai import Crew, LLM, Process
from dotenv import load_dotenv

from agents.boss_agent import create_boss_agent, create_report_task
from agents.design_agent import create_design_agent, create_design_task
from agents.listing_agent import create_listing_agent, create_listing_task
from agents.market_agent import create_market_agent, create_market_research_task
from agents.telegram_agent import create_telegram_agent, create_approval_task
from tools.supabase_client import SupabaseClient

load_dotenv()
logger = logging.getLogger(__name__)


class EtsyAgentsCrew:
    def __init__(self) -> None:
        self.db = SupabaseClient()
        self.llm = LLM(
            model="claude-sonnet-4-6",
            api_key=os.environ["ANTHROPIC_API_KEY"],
            temperature=0.1,
            max_tokens=4096,
        )

    def run(self, run_id: str | None = None) -> dict:
        """
        Execute the full pipeline for a single run.
        Returns a dict with run_id, status, and boss_report.
        """
        if run_id is None:
            run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        logger.info("=" * 60)
        logger.info("Starting EtsyAgentsCrew run: %s", run_id)
        logger.info("=" * 60)

        # Create the run record in Supabase
        self.db.create_run(run_id)
        self.db.log("boss_agent", f"Pipeline started (run_id={run_id})", run_id=run_id)

        try:
            result = self._execute_crew(run_id)
            logger.info("Run %s completed successfully.", run_id)
            return {"run_id": run_id, "status": "completed", "result": str(result)}

        except Exception as exc:
            error_msg = f"Pipeline failed: {exc}"
            logger.error("Run %s FAILED: %s", run_id, exc, exc_info=True)
            self.db.update_run(run_id, status="failed")
            self.db.log("boss_agent", error_msg, level="error", run_id=run_id)
            return {"run_id": run_id, "status": "failed", "error": error_msg}

    def _execute_crew(self, run_id: str):
        # ── Create agents ──────────────────────────────────────────────────
        market_agent = create_market_agent(self.llm, run_id)
        design_agent = create_design_agent(self.llm, run_id)
        telegram_agent = create_telegram_agent(self.llm, run_id)
        listing_agent = create_listing_agent(self.llm, run_id)
        boss_agent = create_boss_agent(self.llm, run_id)

        # ── Create tasks (each depends on previous) ────────────────────────
        market_task = create_market_research_task(market_agent, run_id)
        design_task = create_design_task(design_agent, run_id, context=[market_task])
        approval_task = create_approval_task(telegram_agent, run_id, context=[market_task, design_task])
        listing_task = create_listing_task(listing_agent, run_id, context=[market_task, design_task, approval_task])
        report_task = create_report_task(
            boss_agent,
            run_id,
            context=[market_task, design_task, approval_task, listing_task],
        )

        # ── Assemble and kick off crew ─────────────────────────────────────
        crew = Crew(
            agents=[market_agent, design_agent, telegram_agent, listing_agent],
            tasks=[market_task, design_task, approval_task, listing_task, report_task],
            manager_agent=boss_agent,
            process=Process.hierarchical,
            verbose=True,
            memory=False,
        )

        return crew.kickoff()
