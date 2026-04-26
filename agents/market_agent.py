import json
import logging
from typing import Any

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import Field

from tools.market_scraper import MarketScraper
from tools.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class MarketResearchTool(BaseTool):
    name: str = "market_research_tool"
    description: str = (
        "Search eBay for best-selling digital download products. "
        "Returns top 10 opportunities ranked by opportunity score, "
        "plus the single best recommendation with a suggested listing price."
    )
    run_id: str = Field(default="")
    db: Any = Field(default=None, exclude=True)
    scraper: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "db", SupabaseClient())
        object.__setattr__(self, "scraper", MarketScraper())

    def _run(self, query: str = "") -> str:
        logger.info("[MarketAgent] Starting eBay market research...")
        self.db.log("market_agent", "Starting eBay market research", run_id=self.run_id)

        try:
            result = self.scraper.full_research()
            opportunities = result["opportunities"]
            top = result["top_recommendation"]

            # Save all opportunities to Supabase
            for opp in opportunities:
                self.db.save_market_research(
                    run_id=self.run_id,
                    product_type=opp["product_type"],
                    keywords=opp["keywords"],
                    avg_price=opp["avg_price"],
                    sales_volume=opp["sales_volume"],
                    opportunity_score=opp["opportunity_score"],
                    raw_data={"sample_titles": opp.get("sample_titles", [])},
                )

            self.db.log(
                "market_agent",
                f"Research complete. Top pick: {top['product_type']} (score {top['opportunity_score']})",
                run_id=self.run_id,
            )

            return json.dumps(
                {
                    "status": "success",
                    "total_items_analysed": result["total_items_analysed"],
                    "top_recommendation": {
                        "product_type": top["product_type"],
                        "keywords": top["keywords"],
                        "avg_competitor_price": top["avg_price"],
                        "suggested_price": top["suggested_price"],
                        "opportunity_score": top["opportunity_score"],
                        "reasoning": top["recommendation_reason"],
                    },
                    "all_opportunities": [
                        {
                            "rank": i + 1,
                            "product_type": o["product_type"],
                            "score": o["opportunity_score"],
                            "avg_price": o["avg_price"],
                            "listings_found": o["sales_volume"],
                        }
                        for i, o in enumerate(opportunities[:10])
                    ],
                },
                indent=2,
            )

        except Exception as exc:
            error_msg = f"Market research failed: {exc}"
            logger.error(error_msg)
            self.db.log("market_agent", error_msg, level="error", run_id=self.run_id)
            raise


def create_market_agent(llm: Any, run_id: str) -> Agent:
    tool = MarketResearchTool(run_id=run_id)
    return Agent(
        role="eBay Market Research Specialist",
        goal=(
            "Identify the highest-opportunity digital download products on eBay "
            "by analysing competitor listings, pricing, and sales volume. "
            "Return a clear #1 product recommendation with full reasoning."
        ),
        backstory=(
            "You are an expert eBay market researcher with deep knowledge of the digital "
            "downloads category. You analyse trends, competitor pricing, and demand signals "
            "to find profitable opportunities for new digital product listings."
        ),
        tools=[tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_retry_limit=3,
    )


def create_market_research_task(agent: Agent, run_id: str) -> Task:
    return Task(
        description=(
            f"Conduct a full eBay market research run (run_id: {run_id}). "
            "Use the market_research_tool to search eBay for best-selling digital download products. "
            "Analyse the results and identify the single best product opportunity. "
            "Consider: sales volume, average price, competition level, and profit potential. "
            "Categories to focus on: calendars, planners, trackers, wall art, notebooks."
        ),
        expected_output=(
            "A JSON object with: "
            "(1) top_recommendation — the single best product type with product_type, keywords, "
            "suggested_price, opportunity_score, and a clear reasoning paragraph. "
            "(2) all_opportunities — ranked list of top 10 product types with scores. "
            "The output must be valid JSON that the Design Agent can consume."
        ),
        agent=agent,
    )
