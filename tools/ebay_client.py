import os
import time
import base64
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

load_dotenv()

SANDBOX_BASE = "https://api.sandbox.ebay.com"
PROD_BASE = "https://api.ebay.com"

DIGITAL_CATEGORY_IDS = {
    "pdf": "11116",
    "calendar": "11116",
    "planner": "11116",
    "printable": "11116",
    "wall_art": "11116",
    "tracker": "11116",
    "notebook": "11116",
}

EBAY_DIGITAL_CATEGORY = "11116"


class EbayClient:
    def __init__(self) -> None:
        self.app_id = os.environ["EBAY_APP_ID"]
        self.cert_id = os.environ["EBAY_CERT_ID"]
        self.dev_id = os.environ["EBAY_DEV_ID"]
        self.user_token = os.environ["EBAY_USER_TOKEN"]
        self.sandbox = os.getenv("EBAY_SANDBOX_MODE", "true").lower() == "true"
        self.base_url = SANDBOX_BASE if self.sandbox else PROD_BASE
        self._app_token: str | None = None
        self._app_token_expiry: float = 0.0

    # ── Authentication ────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get_app_token(self) -> str:
        if self._app_token and time.time() < self._app_token_expiry:
            return self._app_token

        credentials = base64.b64encode(f"{self.app_id}:{self.cert_id}".encode()).decode()
        resp = requests.post(
            f"{self.base_url}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._app_token = data["access_token"]
        self._app_token_expiry = time.time() + data.get("expires_in", 7200) - 60
        return self._app_token

    def _browse_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_app_token()}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Content-Type": "application/json",
        }

    def _sell_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── Browse API ────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def search_listings(self, keywords: str, limit: int = 50) -> list[dict]:
        params = {
            "q": keywords,
            "category_ids": EBAY_DIGITAL_CATEGORY,
            "limit": limit,
            "sort": "newlyListed",
            "filter": "buyingOptions:{FIXED_PRICE}",
        }
        resp = requests.get(
            f"{self.base_url}/buy/browse/v1/item_summary/search",
            headers=self._browse_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("itemSummaries", [])

    def extract_product_metrics(self, items: list[dict]) -> list[dict]:
        results = []
        for item in items:
            price_val = 0.0
            price_info = item.get("price", {})
            if price_info:
                try:
                    price_val = float(price_info.get("value", 0))
                except (ValueError, TypeError):
                    price_val = 0.0

            results.append(
                {
                    "title": item.get("title", ""),
                    "price": price_val,
                    "seller": item.get("seller", {}).get("username", ""),
                    "feedback_score": item.get("seller", {}).get("feedbackScore", 0),
                    "condition": item.get("condition", ""),
                    "item_id": item.get("itemId", ""),
                    "image_url": item.get("image", {}).get("imageUrl", ""),
                    "categories": [c.get("categoryName", "") for c in item.get("categories", [])],
                }
            )
        return results

    # ── Inventory API (create listings) ──────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_inventory_item(self, sku: str, product_data: dict) -> bool:
        payload = {
            "availability": {
                "shipToLocationAvailability": {"quantity": 9999}
            },
            "condition": "NEW",
            "product": {
                "title": product_data["title"],
                "description": product_data["description"],
                "imageUrls": product_data.get("image_urls", []),
                "aspects": product_data.get("aspects", {}),
            },
        }
        resp = requests.put(
            f"{self.base_url}/sell/inventory/v1/inventory_item/{sku}",
            headers=self._sell_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_offer(self, sku: str, price: float, product_type: str) -> str:
        payload = {
            "sku": sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "availableQuantity": 9999,
            "categoryId": EBAY_DIGITAL_CATEGORY,
            "listingDescription": "",
            "listingPolicies": {
                "fulfillmentPolicyId": self._get_fulfillment_policy_id(),
                "paymentPolicyId": self._get_payment_policy_id(),
                "returnPolicyId": self._get_return_policy_id(),
            },
            "pricingSummary": {
                "price": {"value": str(price), "currency": "USD"}
            },
            "listingDuration": "GTC",
        }
        resp = requests.post(
            f"{self.base_url}/sell/account/v1/offer",
            headers=self._sell_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["offerId"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def publish_offer(self, offer_id: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/sell/account/v1/offer/{offer_id}/publish",
            headers=self._sell_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        listing_id = data.get("listingId", "")
        env_prefix = "sandbox." if self.sandbox else ""
        ebay_url = f"https://{env_prefix}ebay.com/itm/{listing_id}"
        return {"listing_id": listing_id, "url": ebay_url}

    def create_full_listing(self, sku: str, product_data: dict, price: float) -> dict:
        """End-to-end: create inventory item → offer → publish. Returns listing info."""
        self.create_inventory_item(sku, product_data)
        offer_id = self.create_offer(sku, price, product_data.get("product_type", "pdf"))
        return self.publish_offer(offer_id)

    # ── Account Policies ──────────────────────────────────────────────────────

    def _get_fulfillment_policy_id(self) -> str:
        """Return the first digital-delivery fulfillment policy found, or raise."""
        resp = requests.get(
            f"{self.base_url}/sell/account/v1/fulfillment_policy",
            headers=self._sell_headers(),
            params={"marketplace_id": "EBAY_US"},
            timeout=30,
        )
        resp.raise_for_status()
        policies = resp.json().get("fulfillmentPolicies", [])
        if not policies:
            raise RuntimeError(
                "No fulfillment policies found. Create one in Seller Hub → Account → Shipping policies "
                "(choose 'No shipping – digital delivery')."
            )
        return policies[0]["fulfillmentPolicyId"]

    def _get_payment_policy_id(self) -> str:
        resp = requests.get(
            f"{self.base_url}/sell/account/v1/payment_policy",
            headers=self._sell_headers(),
            params={"marketplace_id": "EBAY_US"},
            timeout=30,
        )
        resp.raise_for_status()
        policies = resp.json().get("paymentPolicies", [])
        if not policies:
            raise RuntimeError("No payment policies found. Create one in Seller Hub → Account → Payment policies.")
        return policies[0]["paymentPolicyId"]

    def _get_return_policy_id(self) -> str:
        resp = requests.get(
            f"{self.base_url}/sell/account/v1/return_policy",
            headers=self._sell_headers(),
            params={"marketplace_id": "EBAY_US"},
            timeout=30,
        )
        resp.raise_for_status()
        policies = resp.json().get("returnPolicies", [])
        if not policies:
            raise RuntimeError("No return policies found. Create one in Seller Hub → Account → Return policies.")
        return policies[0]["returnPolicyId"]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def build_listing_description(self, product_info: dict) -> str:
        product_type = product_info.get("product_type", "Digital Product")
        title = product_info.get("title", "")
        keywords = product_info.get("keywords", [])

        return f"""<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<h2 style="color: #2c3e50;">{title}</h2>

<h3 style="color: #3498db;">What You'll Receive</h3>
<ul>
  <li>High-quality PDF file — ready to print at home or at any print shop</li>
  <li>US Letter size (8.5" × 11") — fits standard printers</li>
  <li>Instant digital download — no physical item shipped</li>
  <li>Compatible with Adobe Acrobat Reader (free) and most PDF viewers</li>
</ul>

<h3 style="color: #3498db;">About This {product_type.replace('_', ' ').title()}</h3>
<p>This beautifully designed {product_type.replace('_', ' ')} is perfect for staying organized and productive.
Created with attention to detail and a clean, modern aesthetic.</p>

<h3 style="color: #3498db;">How It Works</h3>
<ol>
  <li>Purchase this listing</li>
  <li>Instantly receive a download link via eBay messages</li>
  <li>Download your PDF file</li>
  <li>Print and use immediately!</li>
</ol>

<p style="font-size: 12px; color: #7f8c8d;">
Keywords: {', '.join(keywords[:10])}
</p>
</div>"""

    def build_item_specifics(self, product_type: str) -> dict:
        base = {
            "Format": ["PDF"],
            "File Format": ["PDF"],
            "Compatible Software": ["Adobe Acrobat Reader", "Any PDF Viewer"],
            "Digital Download": ["Yes"],
            "Instant Download": ["Yes"],
            "Paper Size": ["US Letter 8.5x11"],
        }
        type_specifics = {
            "calendar": {"Type": ["Calendar"], "Year": ["2026"]},
            "planner": {"Type": ["Planner / Organizer"]},
            "habit_tracker": {"Type": ["Habit Tracker"]},
            "budget_tracker": {"Type": ["Budget Tracker / Financial Planner"]},
            "meal_planner": {"Type": ["Meal Planner"]},
            "workout_log": {"Type": ["Workout Log / Fitness Tracker"]},
            "wall_art": {"Type": ["Wall Art / Printable"]},
            "notebook": {"Type": ["Notebook / Journal"]},
        }
        base.update(type_specifics.get(product_type, {}))
        return base
