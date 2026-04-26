import json
import logging
from typing import Any

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import Field

from tools.telegram_client import TelegramClient
from tools.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class TelegramApprovalTool(BaseTool):
    name: str = "telegram_approval_tool"
    description: str = (
        "Send a product approval request to the owner via Telegram with preview image and "
        "market summary. Waits for owner to press APPROVE, SET CUSTOM PRICE, or REJECT. "
        "Input: JSON string with product details. "
        "Output: approval status and final price."
    )
    run_id: str = Field(default="")
    db: Any = Field(default=None, exclude=True)
    tg: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "db", SupabaseClient())
        object.__setattr__(self, "tg", TelegramClient())

    def _run(self, input_json: str) -> str:
        try:
            params = json.loads(input_json) if isinstance(input_json, str) else input_json
        except (json.JSONDecodeError, TypeError):
            params = {}

        product_id = params.get("product_id", "")
        product_title = params.get("product_title", "Digital Product")
        product_type = params.get("product_type", "printable")
        preview_path = params.get("preview_path", "")
        suggested_price = float(params.get("suggested_price", 4.99))
        market_reasoning = params.get("market_reasoning", "High opportunity score based on eBay market research.")

        logger.info("[TelegramAgent] Sending approval request for '%s'", product_title)
        self.db.log(
            "telegram_agent",
            f"Sending Telegram approval request. Suggested price: ${suggested_price:.2f}",
            run_id=self.run_id,
        )

        # Create approval record first
        approval = self.db.create_approval(
            run_id=self.run_id,
            product_id=product_id,
            suggested_price=suggested_price,
        )
        approval_id = approval["id"]

        # Send the Telegram message
        message_id = self.tg.send_approval_request(
            product_name=product_title,
            product_type=product_type,
            preview_image_path=preview_path,
            market_summary=market_reasoning,
            suggested_price=suggested_price,
            run_id=self.run_id,
        )

        # Update approval record with message_id
        self.db.client.table("approval_log").update(
            {"telegram_message_id": message_id}
        ).eq("id", approval_id).execute()

        # Wait for owner response (up to 24h)
        self.db.log(
            "telegram_agent",
            "Waiting for owner approval (timeout: 24 hours)...",
            run_id=self.run_id,
        )
        response = self.tg.wait_for_approval(
            run_id=self.run_id,
            suggested_price=suggested_price,
        )

        status = response["status"]
        final_price = response.get("price", 0.0)

        # Update approval record with decision
        self.db.update_approval(approval_id, status=status, final_price=final_price if status != "rejected" else None)

        self.db.log(
            "telegram_agent",
            f"Approval decision: {status}, final price: ${final_price:.2f}",
            run_id=self.run_id,
        )

        if status == "timeout":
            return json.dumps({"status": "timeout", "message": "No response in 24 hours. Run cancelled."})

        if status == "rejected":
            return json.dumps({"status": "rejected", "message": "Owner rejected this product."})

        return json.dumps(
            {
                "status": "approved",
                "final_price": final_price,
                "product_id": product_id,
                "product_title": product_title,
                "product_type": product_type,
            },
            indent=2,
        )


def create_telegram_agent(llm: Any, run_id: str) -> Agent:
    tool = TelegramApprovalTool(run_id=run_id)
    return Agent(
        role="Telegram Notification & Approval Manager",
        goal=(
            "Get owner approval before any product is listed on eBay. "
            "Send a clear, informative approval request via Telegram and accurately "
            "capture the owner's decision (approve, custom price, or reject)."
        ),
        backstory=(
            "You are the gatekeeper between the automated pipeline and live eBay listings. "
            "You ensure the business owner has full control and visibility over every product "
            "before it goes live. You communicate clearly and professionally."
        ),
        tools=[tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_retry_limit=2,
    )


def create_approval_task(agent: Agent, run_id: str, context: list | None = None) -> Task:
    return Task(
        description=(
            f"Request owner approval via Telegram for the product designed in the previous task "
            f"(run_id: {run_id}). "
            "Extract from the Design Agent output: product_id, product_title, product_type, "
            "preview_path, and the suggested_price from the Market Agent output. "
            "Also include the market reasoning from the Market Agent output. "
            "Use the telegram_approval_tool with a JSON input containing all these fields. "
            "If the result is 'rejected' or 'timeout', report that and stop the pipeline."
        ),
        expected_output=(
            "A JSON object with: status ('approved', 'rejected', or 'timeout'), "
            "final_price (the price approved by the owner), product_id, and product_title. "
            "If status is not 'approved', include a message explaining why the pipeline stopped."
        ),
        agent=agent,
        context=context or [],
    )
