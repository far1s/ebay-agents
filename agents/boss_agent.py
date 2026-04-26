import json
import logging
from typing import Any

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import Field

from tools.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

AGENT_NAMES = ["market_agent", "design_agent", "telegram_agent", "listing_agent"]


class BossReportTool(BaseTool):
    name: str = "boss_report_tool"
    description: str = (
        "Save the Boss Agent's run report to Supabase. Scores each agent's performance "
        "and marks the run as complete. "
        "Input: JSON string with run summary and agent scores."
    )
    run_id: str = Field(default="")
    db: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "db", SupabaseClient())

    def _run(self, input_json: str) -> str:
        try:
            report = json.loads(input_json) if isinstance(input_json, str) else input_json
        except (json.JSONDecodeError, TypeError):
            report = {}

        run_status = report.get("run_status", "completed")
        summary = report.get("summary", "Run completed.")
        agent_scores: dict = report.get("agent_scores", {})

        # Save individual agent performance scores
        for agent_name, score_data in agent_scores.items():
            score = score_data if isinstance(score_data, int) else score_data.get("score", 7)
            notes = "" if isinstance(score_data, int) else score_data.get("notes", "")
            self.db.save_performance(
                run_id=self.run_id,
                agent_name=agent_name,
                score=score,
                notes=notes,
            )

        # Mark run as complete with boss report
        self.db.update_run(
            run_id=self.run_id,
            status=run_status,
            boss_report={"summary": summary, "agent_scores": agent_scores, "details": report},
        )

        self.db.log(
            "boss_agent",
            f"Run {self.run_id} completed with status '{run_status}'. {summary}",
            run_id=self.run_id,
        )

        return json.dumps({"saved": True, "run_id": self.run_id, "status": run_status})


def create_boss_agent(llm: Any, run_id: str) -> Agent:
    tool = BossReportTool(run_id=run_id)
    return Agent(
        role="Operations Manager & Quality Controller",
        goal=(
            "Orchestrate the full eBay digital product pipeline, monitor each agent's output, "
            "score their performance (1–10), write a concise run report, and save it to the database. "
            "Never let a single agent failure crash the entire pipeline."
        ),
        backstory=(
            "You are the CEO of a digital products business. You oversee a team of specialised agents: "
            "a market researcher, a designer, a Telegram coordinator, and an eBay listing specialist. "
            "You set high standards, give clear feedback, and ensure every run is logged and scored. "
            "You recover gracefully from errors and always provide a useful post-run summary."
        ),
        tools=[tool],
        llm=llm,
        verbose=True,
        allow_delegation=True,
        max_retry_limit=2,
    )


def create_report_task(agent: Agent, run_id: str, context: list | None = None) -> Task:
    return Task(
        description=(
            f"Review all agent outputs from this pipeline run (run_id: {run_id}) and write a report. "
            "For each of the 4 agents (market_agent, design_agent, telegram_agent, listing_agent), "
            "score their performance on a 1-10 scale based on: "
            "  - Did they complete their task? "
            "  - Was the output quality high? "
            "  - Were there any errors or retries? "
            "  - Did they follow instructions precisely? "
            "Then write a concise 2–3 sentence summary of the full run. "
            "Finally use the boss_report_tool to save the report. "
            "Input JSON format: "
            '{"run_status": "completed", "summary": "...", '
            '"agent_scores": {"market_agent": {"score": 8, "notes": "..."}, ...}}'
        ),
        expected_output=(
            "Confirmation that the report was saved: a JSON with saved=true, run_id, and status. "
            "Also output a human-readable summary of what happened in this run."
        ),
        agent=agent,
        context=context or [],
    )
