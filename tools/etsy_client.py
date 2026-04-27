import os
import time
import logging
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ETSY_BASE = "https://openapi.etsy.com/v3"

# Etsy taxonomy IDs for digital products
DIGITAL_TAXONOMY_IDS = {
    "calendar": 2078,
    "planner": 2078,
    "habit_tracker": 2078,
    "budget_tracker": 2078,
    "meal_planner": 2078,
    "workout_log": 2078,
    "wall_art": 2078,
    "notebook": 2078,
    "printable": 2078,
}
DEFAULT_TAXONOMY_ID = 2078  # Digital Prints


class EtsyClient:
    def __init__(self) -> None:
        self.api_key = os.environ["ETSY_API_KEY"]
        self.shop_id = os.environ["ETSY_SHOP_ID"]
        self.access_token = os.environ["ETSY_ACCESS_TOKEN"]

    def _public_headers(self) -> dict:
        return {"x-api-key": self.api_key}

    def _auth_headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
        }

    # ── Market Research ───────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def search_listings(self, keywords: str, limit: int = 50) -> list[dict]:
        """Search active Etsy listings. Uses public API (no OAuth needed)."""
        params = {
            "keywords": keywords,
            "limit": min(limit, 100),
            "sort_on": "score",
            "sort_order": "desc",
        }
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{ETSY_BASE}/application/listings/active",
                headers=self._public_headers(),
                params=params,
            )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def extract_product_metrics(self, listings: list[dict]) -> list[dict]:
        """Normalise Etsy listing data to a common dict structure."""
        results = []
        for item in listings:
            price_obj = item.get("price", {})
            divisor = price_obj.get("divisor", 100) or 100
            price_val = price_obj.get("amount", 0) / divisor

            results.append(
                {
                    "title": item.get("title", ""),
                    "price": round(price_val, 2),
                    "shop_id": item.get("shop_id", ""),
                    "listing_id": item.get("listing_id", ""),
                    "num_favorers": item.get("num_favorers", 0),
                    "tags": item.get("tags", []),
                    "taxonomy_id": item.get("taxonomy_id", 0),
                    "image_url": (item.get("images") or [{}])[0].get("url_570xN", ""),
                }
            )
        return results

    # ── Listing Creation ──────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_draft_listing(self, product_data: dict, price: float) -> int:
        """Create a draft listing on Etsy. Returns the listing_id."""
        tags = product_data.get("tags", [])[:13]  # Etsy max 13 tags
        taxonomy_id = DIGITAL_TAXONOMY_IDS.get(product_data.get("product_type", ""), DEFAULT_TAXONOMY_ID)

        payload = {
            "quantity": 999,
            "title": product_data["title"][:140],  # Etsy max 140 chars
            "description": product_data["description"],
            "price": round(price, 2),
            "who_made": "i_did",
            "when_made": "made_to_order",
            "taxonomy_id": taxonomy_id,
            "type": "download",
            "tags": tags,
            "is_digital": True,
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{ETSY_BASE}/application/shops/{self.shop_id}/listings",
                headers={**self._auth_headers(), "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["listing_id"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def upload_listing_image(self, listing_id: int, image_path: str) -> int:
        """Upload a preview image to an Etsy listing. Returns listing_image_id."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with httpx.Client(timeout=60) as client:
            with open(path, "rb") as f:
                resp = client.post(
                    f"{ETSY_BASE}/application/shops/{self.shop_id}/listings/{listing_id}/images",
                    headers=self._auth_headers(),
                    files={"image": (path.name, f, "image/png")},
                    data={"rank": 1},
                )
        resp.raise_for_status()
        return resp.json().get("listing_image_id", 0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def upload_listing_file(self, listing_id: int, file_path: str) -> int:
        """Upload a digital file (PDF) to an Etsy listing. Returns listing_file_id."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with httpx.Client(timeout=120) as client:
            with open(path, "rb") as f:
                resp = client.post(
                    f"{ETSY_BASE}/application/shops/{self.shop_id}/listings/{listing_id}/files",
                    headers=self._auth_headers(),
                    files={"file": (path.name, f, "application/pdf")},
                    data={"rank": 1},
                )
        resp.raise_for_status()
        return resp.json().get("listing_file_id", 0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def publish_listing(self, listing_id: int) -> str:
        """Set listing state to 'active'. Returns the Etsy listing URL."""
        with httpx.Client(timeout=30) as client:
            resp = client.patch(
                f"{ETSY_BASE}/application/listings/{listing_id}",
                headers={**self._auth_headers(), "Content-Type": "application/json"},
                json={"state": "active"},
            )
        resp.raise_for_status()
        return f"https://www.etsy.com/listing/{listing_id}"

    def create_full_listing(self, product_data: dict, price: float, pdf_path: str = "", image_path: str = "") -> dict:
        """End-to-end: draft → upload image → upload file → publish. Returns listing info."""
        listing_id = self.create_draft_listing(product_data, price)

        if image_path and Path(image_path).exists():
            try:
                self.upload_listing_image(listing_id, image_path)
            except Exception as exc:
                logger.warning("Image upload failed (listing will proceed without image): %s", exc)

        if pdf_path and Path(pdf_path).exists():
            try:
                self.upload_listing_file(listing_id, pdf_path)
            except Exception as exc:
                logger.warning("File upload failed: %s", exc)

        etsy_url = self.publish_listing(listing_id)
        return {"listing_id": listing_id, "url": etsy_url}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def build_listing_description(self, product_info: dict) -> str:
        product_type = product_info.get("product_type", "Digital Product").replace("_", " ").title()
        title = product_info.get("title", "")
        keywords = product_info.get("keywords", [])

        return f"""{title}

★ INSTANT DIGITAL DOWNLOAD ★

What You'll Receive:
• High-quality PDF file — ready to print at home or at any print shop
• US Letter size (8.5" × 11") — fits standard printers
• Instant download after purchase — no waiting, no shipping
• Compatible with Adobe Acrobat Reader (free) and any PDF viewer

About This {product_type}:
This beautifully designed {product_type.lower()} is perfect for staying organised and productive.
Created with attention to detail and a clean, modern aesthetic that you'll love using every day.

How It Works:
1. Purchase this listing
2. Immediately receive a download link via Etsy
3. Download your PDF file
4. Print and use right away!

Please Note:
• This is a DIGITAL item — no physical product will be shipped
• Files are for personal use only (not for resale or redistribution)
• Due to the digital nature of this product, all sales are final

Keywords: {', '.join(keywords[:10])}"""

    def build_tags(self, product_type: str, keywords: list[str]) -> list[str]:
        """Build up to 13 Etsy tags from product type and research keywords."""
        base_tags = {
            "calendar": ["printable calendar", "digital calendar", "2026 calendar", "monthly planner"],
            "planner": ["printable planner", "digital planner", "weekly planner", "daily planner"],
            "habit_tracker": ["habit tracker", "daily tracker", "printable tracker", "habit log"],
            "budget_tracker": ["budget tracker", "finance planner", "expense tracker", "money planner"],
            "meal_planner": ["meal planner", "food planner", "weekly menu", "grocery list"],
            "workout_log": ["workout log", "fitness tracker", "exercise log", "gym tracker"],
            "wall_art": ["printable wall art", "digital print", "home decor print", "quote print"],
            "notebook": ["printable notebook", "dot grid notebook", "lined journal", "journal pages"],
        }
        tags = base_tags.get(product_type, ["printable", "digital download"])
        tags += ["instant download", "printable pdf", "digital download"]

        # Add unique keywords that aren't already in tags
        for kw in keywords:
            if len(tags) >= 13:
                break
            cleaned = kw.lower().strip()[:20]  # Etsy tag max length is 20 chars
            if cleaned and cleaned not in tags:
                tags.append(cleaned)

        return tags[:13]
