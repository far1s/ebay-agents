import re
import time
import logging
from collections import Counter

from dotenv import load_dotenv

from .etsy_client import EtsyClient

load_dotenv()
logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "digital planner 2026 printable",
    "printable PDF calendar 2026",
    "digital download notebook printable",
    "printable wall art digital",
    "habit tracker printable PDF",
    "budget tracker printable PDF",
    "meal planner printable digital",
    "workout log printable fitness",
    "dot grid notebook printable",
    "weekly planner printable PDF",
]

PRODUCT_TYPE_KEYWORDS = {
    "calendar": ["calendar", "monthly", "yearly", "planner 2026", "2026 calendar"],
    "weekly_planner": ["weekly planner", "week planner", "weekly schedule"],
    "habit_tracker": ["habit tracker", "habit log", "daily tracker"],
    "budget_tracker": ["budget tracker", "finance tracker", "expense tracker", "money planner"],
    "meal_planner": ["meal planner", "food planner", "recipe planner", "grocery list"],
    "workout_log": ["workout log", "fitness tracker", "exercise log", "gym tracker"],
    "wall_art": ["wall art", "printable art", "quote print", "home decor print"],
    "notebook": ["notebook", "dot grid", "lined journal", "journal pages"],
}


class MarketScraper:
    def __init__(self) -> None:
        self.etsy = EtsyClient()

    def research_all_categories(self) -> list[dict]:
        """Search all predefined queries on Etsy and aggregate results."""
        all_items: list[dict] = []
        for query in SEARCH_QUERIES:
            logger.info("Searching Etsy for: %s", query)
            try:
                raw_items = self.etsy.search_listings(query, limit=30)
                metrics = self.etsy.extract_product_metrics(raw_items)
                for item in metrics:
                    item["search_query"] = query
                all_items.extend(metrics)
                time.sleep(0.5)
            except Exception as exc:
                logger.warning("Search failed for '%s': %s", query, exc)

        return all_items

    def classify_product_type(self, title: str) -> str:
        title_lower = title.lower()
        for product_type, keywords in PRODUCT_TYPE_KEYWORDS.items():
            if any(kw in title_lower for kw in keywords):
                return product_type
        return "printable"

    def extract_keywords(self, titles: list[str]) -> list[str]:
        stop_words = {
            "the", "a", "an", "and", "or", "for", "to", "in", "of", "with",
            "pdf", "digital", "download", "printable", "instant", "file",
            "print", "at", "your", "on", "is", "be", "are", "this",
        }
        words: list[str] = []
        for title in titles:
            clean = re.sub(r"[^a-zA-Z0-9 ]", " ", title.lower())
            words.extend(w for w in clean.split() if w not in stop_words and len(w) > 2)

        counter = Counter(words)
        return [word for word, _ in counter.most_common(20)]

    def score_opportunity(self, items: list[dict]) -> float:
        """Score an opportunity group using price and Etsy favorers as proxy for demand."""
        if not items:
            return 0.0

        prices = [i["price"] for i in items if i["price"] > 0]
        avg_price = sum(prices) / len(prices) if prices else 0.0

        # num_favorers is Etsy's closest public proxy for popularity
        total_favorers = sum(i.get("num_favorers", 0) for i in items)
        avg_favorers = total_favorers / len(items) if items else 0

        if 3 <= avg_price <= 15:
            price_score = 10.0
        elif avg_price < 3:
            price_score = avg_price / 3 * 10
        else:
            price_score = max(0, 10 - (avg_price - 15) / 5)

        # Volume score — more listings + higher favorers = proven market
        volume_score = min(10.0, len(items) / 5)
        favorer_score = min(10.0, avg_favorers / 100)

        return round((price_score * 0.5 + volume_score * 0.3 + favorer_score * 0.2), 2)

    def rank_opportunities(self, all_items: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = {}
        for item in all_items:
            ptype = self.classify_product_type(item["title"])
            grouped.setdefault(ptype, []).append(item)

        opportunities: list[dict] = []
        for product_type, items in grouped.items():
            prices = [i["price"] for i in items if i["price"] > 0]
            avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0
            keywords = self.extract_keywords([i["title"] for i in items])
            score = self.score_opportunity(items)

            opportunities.append(
                {
                    "product_type": product_type,
                    "keywords": keywords[:10],
                    "avg_price": avg_price,
                    "sales_volume": len(items),
                    "opportunity_score": score,
                    "sample_titles": [i["title"] for i in items[:5]],
                    "raw_items": items[:10],
                }
            )

        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return opportunities[:10]

    def get_top_recommendation(self, opportunities: list[dict]) -> dict:
        if not opportunities:
            return self._fallback_opportunity()

        top = opportunities[0]
        suggested_price = round(max(2.99, top["avg_price"] * 1.4), 2)
        top["suggested_price"] = suggested_price
        top["recommendation_reason"] = (
            f"'{top['product_type'].replace('_', ' ').title()}' has the highest opportunity score "
            f"({top['opportunity_score']}/10) with {top['sales_volume']} listings found on Etsy "
            f"at an average price of ${top['avg_price']:.2f}. "
            f"Suggested listing price ${suggested_price:.2f} gives ~40% margin over avg competitor price."
        )
        return top

    def _fallback_opportunity(self) -> dict:
        """Return a safe default if the Etsy API returns no results."""
        return {
            "product_type": "calendar",
            "keywords": ["2026 calendar", "monthly planner", "printable", "wall calendar", "digital download"],
            "avg_price": 3.99,
            "sales_volume": 50,
            "opportunity_score": 8.5,
            "suggested_price": 4.99,
            "sample_titles": ["2026 Monthly Calendar Printable PDF", "Printable Wall Calendar 2026"],
            "raw_items": [],
            "recommendation_reason": (
                "2026 calendars are consistently in demand and have strong Etsy search volume. "
                "Suggested price $4.99 is competitive and profitable."
            ),
        }

    def full_research(self) -> dict:
        logger.info("Starting full Etsy market research...")
        all_items = self.research_all_categories()

        if not all_items:
            logger.warning("No items found from Etsy API. Using fallback data.")
            top = self._fallback_opportunity()
            return {
                "opportunities": [top],
                "top_recommendation": top,
                "total_items_analysed": 0,
            }

        opportunities = self.rank_opportunities(all_items)
        top = self.get_top_recommendation(opportunities)

        logger.info(
            "Etsy market research complete. Top pick: %s (score %.1f)",
            top["product_type"],
            top["opportunity_score"],
        )

        return {
            "opportunities": opportunities,
            "top_recommendation": top,
            "total_items_analysed": len(all_items),
        }
