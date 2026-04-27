import json
import logging
from typing import Any

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import Field

from tools.pdf_generator import PDFGenerator
from tools.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class PDFDesignTool(BaseTool):
    name: str = "pdf_design_tool"
    description: str = (
        "Generate professional PDF digital products in 3 style variations (modern, classic, minimal). "
        "Input: JSON string with product_type and keywords. "
        "Output: paths to the best PDF file and its preview image, plus a quality score."
    )
    run_id: str = Field(default="")
    db: Any = Field(default=None, exclude=True)
    generator: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "db", SupabaseClient())
        object.__setattr__(self, "generator", PDFGenerator())

    def _run(self, input_json: str) -> str:
        try:
            params = json.loads(input_json) if isinstance(input_json, str) else input_json
        except (json.JSONDecodeError, TypeError):
            params = {"product_type": "calendar", "keywords": []}

        product_type = params.get("product_type", "calendar")
        keywords = params.get("keywords", [])

        logger.info("[DesignAgent] Generating PDFs for product_type=%s", product_type)
        self.db.log(
            "design_agent",
            f"Generating PDFs for product_type={product_type}",
            run_id=self.run_id,
        )

        try:
            variations = self.generator.generate_product(product_type, self.run_id)
            if not variations:
                raise RuntimeError("No PDF variations were generated")

            best = self.generator.select_best_variation(variations)

            # Save best variation to Supabase
            product_title = _build_title(product_type, keywords)
            record = self.db.save_generated_product(
                run_id=self.run_id,
                product_type=product_type,
                file_path=best["file_path"],
                preview_path=best["preview_path"],
                design_score=best["design_score"],
                metadata={
                    "style": best["style"],
                    "keywords": keywords,
                    "title": product_title,
                    "all_variations": [
                        {"style": v["style"], "score": v["design_score"], "path": v["file_path"]}
                        for v in variations
                    ],
                },
            )

            self.db.log(
                "design_agent",
                f"Best design: {best['style']} style, score {best['design_score']}/10",
                run_id=self.run_id,
            )

            return json.dumps(
                {
                    "status": "success",
                    "product_id": record["id"],
                    "product_type": product_type,
                    "product_title": product_title,
                    "best_style": best["style"],
                    "design_score": best["design_score"],
                    "pdf_path": best["file_path"],
                    "preview_path": best["preview_path"],
                    "keywords": keywords,
                    "all_variations": [
                        {"style": v["style"], "score": v["design_score"]}
                        for v in variations
                    ],
                },
                indent=2,
            )

        except Exception as exc:
            error_msg = f"PDF generation failed: {exc}"
            logger.error(error_msg)
            self.db.log("design_agent", error_msg, level="error", run_id=self.run_id)
            raise


def _build_title(product_type: str, keywords: list[str]) -> str:
    base_titles = {
        "calendar": "2026 Monthly Calendar Printable PDF Instant Download",
        "weekly_planner": "Weekly Planner Printable PDF Digital Download Organizer",
        "habit_tracker": "Habit Tracker Printable PDF Daily Habit Log Instant Download",
        "budget_tracker": "Budget Tracker Printable PDF Monthly Finance Planner",
        "meal_planner": "Meal Planner Printable PDF Weekly Menu Planner Instant Download",
        "workout_log": "Workout Log Printable PDF Fitness Tracker Instant Download",
        "wall_art": "Inspirational Wall Art Printable PDF Motivational Print Instant Download",
        "notebook": "Lined Notebook Printable PDF 100 Pages Instant Download",
    }
    base = base_titles.get(product_type, "Digital Download Printable PDF")
    # Trim to Etsy's 80-char limit
    if len(base) > 80:
        base = base[:77] + "..."
    return base


def create_design_agent(llm: Any, run_id: str) -> Agent:
    tool = PDFDesignTool(run_id=run_id)
    return Agent(
        role="Professional PDF Product Designer",
        goal=(
            "Create high-quality, print-ready PDF digital products based on market research. "
            "Generate 3 style variations and select the best one. "
            "Every product must score at least 7/10 for quality."
        ),
        backstory=(
            "You are a professional graphic designer specialising in printable digital products. "
            "You understand what makes a product look polished, sell well, and stand out on Etsy. "
            "You create clean, functional designs that customers love."
        ),
        tools=[tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_retry_limit=3,
    )


def create_design_task(agent: Agent, run_id: str, context: list | None = None) -> Task:
    return Task(
        description=(
            f"Create a professional PDF digital product (run_id: {run_id}). "
            "Read the market research output from the previous task to determine the product_type and keywords. "
            "Use the pdf_design_tool with a JSON input like: "
            '{"product_type": "<type>", "keywords": ["kw1", "kw2", ...]}. '
            "The tool will generate 3 style variations and pick the best. "
            "If the design score is below 7, retry with a different product_type from the alternatives list."
        ),
        expected_output=(
            "A JSON object with: product_id (Supabase UUID), product_title (Etsy-ready title, max 80 chars), "
            "product_type, design_score (1-10), pdf_path (local file path), "
            "preview_path (PNG thumbnail path), and keywords list."
        ),
        agent=agent,
        context=context or [],
    )
