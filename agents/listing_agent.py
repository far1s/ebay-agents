import json
import logging
from typing import Any

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import Field

from tools.etsy_client import EtsyClient
from tools.telegram_client import TelegramClient
from tools.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class EtsyListingTool(BaseTool):
    name: str = "etsy_listing_tool"
    description: str = (
        "Create a live Etsy listing for an approved digital product. "
        "Input: JSON string with product details and approved price. "
        "Output: Etsy listing ID and URL."
    )
    run_id: str = Field(default="")
    db: Any = Field(default=None, exclude=True)
    etsy: Any = Field(default=None, exclude=True)
    tg: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "db", SupabaseClient())
        object.__setattr__(self, "etsy", EtsyClient())
        object.__setattr__(self, "tg", TelegramClient())

    def _run(self, input_json: str) -> str:
        try:
            params = json.loads(input_json) if isinstance(input_json, str) else input_json
        except (json.JSONDecodeError, TypeError):
            params = {}

        status = params.get("status", "")
        if status != "approved":
            return json.dumps({"status": "skipped", "reason": f"Approval status was '{status}', not listing."})

        product_id = params.get("product_id", "")
        product_title = params.get("product_title", "Digital Product Printable PDF")
        product_type = params.get("product_type", "printable")
        price = float(params.get("final_price", 4.99))
        keywords = params.get("keywords", [])
        pdf_path = params.get("pdf_path", "")
        preview_path = params.get("preview_path", "")

        logger.info("[ListingAgent] Creating Etsy listing: '%s' at $%.2f", product_title, price)
        self.db.log(
            "listing_agent",
            f"Creating Etsy listing: '{product_title}' at ${price:.2f}",
            run_id=self.run_id,
        )

        description = self.etsy.build_listing_description(
            {
                "title": product_title,
                "product_type": product_type,
                "keywords": keywords,
            }
        )
        tags = self.etsy.build_tags(product_type, keywords)

        product_data = {
            "title": product_title[:140],
            "description": description,
            "product_type": product_type,
            "tags": tags,
        }

        try:
            listing_info = self.etsy.create_full_listing(product_data, price, pdf_path, preview_path)
            listing_id = listing_info["listing_id"]
            etsy_url = listing_info["url"]

            self.db.save_listing(
                run_id=self.run_id,
                product_id=product_id,
                etsy_listing_id=str(listing_id),
                etsy_url=etsy_url,
                title=product_title,
                price=price,
            )

            self.db.log(
                "listing_agent",
                f"Etsy listing created: {listing_id} at ${price:.2f}",
                run_id=self.run_id,
            )

            self.tg.send_listing_confirmation(product_title, price, etsy_url)

            return json.dumps(
                {
                    "status": "success",
                    "listing_id": listing_id,
                    "etsy_url": etsy_url,
                    "title": product_title,
                    "price": price,
                },
                indent=2,
            )

        except Exception as exc:
            error_msg = f"Etsy listing failed: {exc}"
            logger.error(error_msg)
            self.db.log("listing_agent", error_msg, level="error", run_id=self.run_id)
            self.tg.send_error_notification(self.run_id, error_msg)
            raise


def create_listing_agent(llm: Any, run_id: str) -> Agent:
    tool = EtsyListingTool(run_id=run_id)
    return Agent(
        role="Etsy Listing Specialist",
        goal=(
            "Create optimised, professional Etsy listings for approved digital products. "
            "Write SEO-optimised titles (max 140 chars), compelling descriptions, and set up to 13 relevant tags. "
            "Ensure every listing is configured as a digital download with the correct taxonomy."
        ),
        backstory=(
            "You are an experienced Etsy seller with expertise in digital downloads. "
            "You know exactly how to structure listings to maximise Etsy search visibility and conversions. "
            "You always write clear, accurate descriptions and use the right keywords and tags."
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
            f"Create an Etsy listing for the approved product (run_id: {run_id}). "
            "Read the approval output from the Telegram Agent — if status is not 'approved', skip this task. "
            "Combine data from all previous tasks: "
            "- product_id, product_title, product_type, pdf_path, preview_path from Design Agent output "
            "- keywords from Market Agent output "
            "- final_price from Telegram Agent output "
            "Use the etsy_listing_tool with all these combined fields in the JSON input. "
            "After successful listing, you're done."
        ),
        expected_output=(
            "A JSON object with: status ('success' or 'skipped'), listing_id (Etsy listing ID), "
            "etsy_url (full URL to the listing), title, and price. "
            "If skipped, include a reason."
        ),
        agent=agent,
        context=context or [],
    )
