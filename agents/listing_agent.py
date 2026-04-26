import json
import logging
import uuid
from pathlib import Path
from typing import Any

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import Field

from tools.ebay_client import EbayClient
from tools.telegram_client import TelegramClient
from tools.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class EbayListingTool(BaseTool):
    name: str = "ebay_listing_tool"
    description: str = (
        "Create a live eBay listing for an approved digital product. "
        "Input: JSON string with product details and approved price. "
        "Output: eBay listing ID and URL."
    )
    run_id: str = Field(default="")
    db: Any = Field(default=None, exclude=True)
    ebay: Any = Field(default=None, exclude=True)
    tg: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "db", SupabaseClient())
        object.__setattr__(self, "ebay", EbayClient())
        object.__setattr__(self, "tg", TelegramClient())

    def _run(self, input_json: str) -> str:
        try:
            params = json.loads(input_json) if isinstance(input_json, str) else input_json
        except (json.JSONDecodeError, TypeError):
            params = {}

        # Validate approval status
        status = params.get("status", "")
        if status != "approved":
            return json.dumps({"status": "skipped", "reason": f"Approval status was '{status}', not listing."})

        product_id = params.get("product_id", "")
        product_title = params.get("product_title", "Digital Product Printable PDF")
        product_type = params.get("product_type", "printable")
        price = float(params.get("final_price", 4.99))
        keywords = params.get("keywords", [])
        pdf_path = params.get("pdf_path", "")

        logger.info("[ListingAgent] Creating eBay listing: '%s' at $%.2f", product_title, price)
        self.db.log(
            "listing_agent",
            f"Creating eBay listing: '{product_title}' at ${price:.2f}",
            run_id=self.run_id,
        )

        # Build listing data
        description = self.ebay.build_listing_description(
            {
                "title": product_title,
                "product_type": product_type,
                "keywords": keywords,
            }
        )
        item_specifics = self.ebay.build_item_specifics(product_type)

        # Generate a unique SKU
        sku = f"EA-{self.run_id[:8]}-{uuid.uuid4().hex[:8]}".upper()

        product_data = {
            "title": product_title[:80],
            "description": description,
            "image_urls": [],  # eBay image hosting not required for sandbox
            "aspects": item_specifics,
            "product_type": product_type,
        }

        try:
            listing_info = self.ebay.create_full_listing(sku, product_data, price)
            listing_id = listing_info["listing_id"]
            ebay_url = listing_info["url"]

            # Save to Supabase
            self.db.save_listing(
                run_id=self.run_id,
                product_id=product_id,
                ebay_listing_id=listing_id,
                ebay_url=ebay_url,
                title=product_title,
                price=price,
            )

            self.db.log(
                "listing_agent",
                f"eBay listing created: {listing_id} at ${price:.2f}",
                run_id=self.run_id,
            )

            # Send Telegram confirmation
            self.tg.send_listing_confirmation(product_title, price, ebay_url)

            return json.dumps(
                {
                    "status": "success",
                    "listing_id": listing_id,
                    "ebay_url": ebay_url,
                    "title": product_title,
                    "price": price,
                    "sku": sku,
                },
                indent=2,
            )

        except Exception as exc:
            error_msg = f"eBay listing failed: {exc}"
            logger.error(error_msg)
            self.db.log("listing_agent", error_msg, level="error", run_id=self.run_id)
            self.tg.send_error_notification(self.run_id, error_msg)
            raise


def create_listing_agent(llm: Any, run_id: str) -> Agent:
    tool = EbayListingTool(run_id=run_id)
    return Agent(
        role="eBay Listing Specialist",
        goal=(
            "Create optimised, professional eBay listings for approved digital products. "
            "Write SEO-optimised titles, compelling descriptions, and set all required item specifics. "
            "Ensure every listing is configured for instant digital download delivery."
        ),
        backstory=(
            "You are an experienced eBay seller with expertise in digital downloads. "
            "You know exactly how to structure listings to maximise visibility and conversions. "
            "You always write clear, accurate descriptions and use the right keywords."
        ),
        tools=[tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_retry_limit=3,
    )


def create_listing_task(agent: Agent, run_id: str, context: list | None = None) -> Task:
    return Task(
        description=(
            f"Create an eBay listing for the approved product (run_id: {run_id}). "
            "Read the approval output from the Telegram Agent — if status is not 'approved', skip this task. "
            "Combine data from all previous tasks: "
            "- product_id, product_title, product_type, pdf_path from Design Agent output "
            "- keywords from Market Agent output "
            "- final_price from Telegram Agent output "
            "Use the ebay_listing_tool with all these combined fields in the JSON input. "
            "After successful listing, you're done."
        ),
        expected_output=(
            "A JSON object with: status ('success' or 'skipped'), listing_id (eBay item ID), "
            "ebay_url (full URL to the listing), title, price, and sku. "
            "If skipped, include a reason."
        ),
        agent=agent,
        context=context or [],
    )
