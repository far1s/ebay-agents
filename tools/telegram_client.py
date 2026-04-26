import os
import time
import logging
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

APPROVAL_TIMEOUT_SECONDS = 86400  # 24 hours
POLL_INTERVAL_SECONDS = 10


class TelegramClient:
    def __init__(self) -> None:
        self.token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.chat_id = os.environ["TELEGRAM_CHAT_ID"]
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._last_update_id: int = 0

    # ── Sending ───────────────────────────────────────────────────────────────

    def send_message(self, text: str, parse_mode: str = "HTML") -> dict:
        resp = requests.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("result", {})

    def send_photo(
        self,
        photo_path: str,
        caption: str,
        reply_markup: dict | None = None,
        parse_mode: str = "HTML",
    ) -> dict:
        data: dict[str, Any] = {
            "chat_id": self.chat_id,
            "caption": caption,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            import json
            data["reply_markup"] = json.dumps(reply_markup)

        with open(photo_path, "rb") as photo_file:
            resp = requests.post(
                f"{self.base_url}/sendPhoto",
                data=data,
                files={"photo": photo_file},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json().get("result", {})

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        requests.post(
            f"{self.base_url}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=15,
        )

    # ── Polling ───────────────────────────────────────────────────────────────

    def get_updates(self, offset: int = 0, timeout: int = 5) -> list[dict]:
        try:
            resp = requests.get(
                f"{self.base_url}/getUpdates",
                params={"offset": offset, "timeout": timeout},
                timeout=timeout + 10,
            )
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception as exc:
            logger.warning("getUpdates failed: %s", exc)
            return []

    # ── Approval Flow ─────────────────────────────────────────────────────────

    def send_approval_request(
        self,
        product_name: str,
        product_type: str,
        preview_image_path: str,
        market_summary: str,
        suggested_price: float,
        run_id: str,
    ) -> int:
        """Send approval message with inline keyboard. Returns Telegram message_id."""
        caption = (
            f"<b>🛒 New Product Ready for Listing</b>\n\n"
            f"<b>Product:</b> {product_name}\n"
            f"<b>Type:</b> {product_type.replace('_', ' ').title()}\n"
            f"<b>Run ID:</b> <code>{run_id}</code>\n\n"
            f"<b>📊 Why this product?</b>\n{market_summary}\n\n"
            f"<b>💰 Suggested Price:</b> <b>${suggested_price:.2f}</b>\n"
            f"  (Based on competitor analysis + 40% margin)\n\n"
            f"Approve to list immediately on eBay, or set a custom price."
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": f"✅ APPROVE  (${suggested_price:.2f})",
                        "callback_data": f"approve:{run_id}:{suggested_price}",
                    },
                ],
                [
                    {
                        "text": "✏️ SET CUSTOM PRICE",
                        "callback_data": f"custom_price:{run_id}",
                    },
                ],
                [
                    {
                        "text": "❌ REJECT",
                        "callback_data": f"reject:{run_id}",
                    }
                ],
            ]
        }

        if preview_image_path and Path(preview_image_path).exists():
            result = self.send_photo(preview_image_path, caption, reply_markup)
        else:
            result = self.send_message(caption)

        return result.get("message_id", 0)

    def wait_for_approval(
        self,
        run_id: str,
        suggested_price: float,
        timeout_seconds: int = APPROVAL_TIMEOUT_SECONDS,
    ) -> dict:
        """
        Poll Telegram for a callback query matching run_id.
        Returns dict: {"status": "approved"|"rejected"|"custom_price"|"timeout", "price": float}
        """
        deadline = time.time() + timeout_seconds
        waiting_for_price = False

        while time.time() < deadline:
            updates = self.get_updates(offset=self._last_update_id + 1, timeout=POLL_INTERVAL_SECONDS)

            for update in updates:
                update_id = update.get("update_id", 0)
                if update_id > self._last_update_id:
                    self._last_update_id = update_id

                # Handle inline button presses
                callback = update.get("callback_query")
                if callback:
                    self.answer_callback_query(callback["id"])
                    data = callback.get("data", "")

                    if f"approve:{run_id}" in data:
                        price = float(data.split(":")[2])
                        self.send_message(f"✅ <b>Approved!</b> Listing at <b>${price:.2f}</b>\nCreating eBay listing now...")
                        return {"status": "approved", "price": price}

                    if f"reject:{run_id}" in data:
                        self.send_message("❌ Rejected. This run has been cancelled.")
                        return {"status": "rejected", "price": 0.0}

                    if f"custom_price:{run_id}" in data:
                        self.send_message(
                            "✏️ Please type your custom price (numbers only, e.g. <code>4.99</code>):"
                        )
                        waiting_for_price = True

                # Handle text reply when waiting for custom price
                if waiting_for_price:
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    if text:
                        try:
                            price = float(text.replace("$", "").replace(",", ""))
                            self.send_message(
                                f"✅ <b>Custom price set to ${price:.2f}</b>\nCreating eBay listing now..."
                            )
                            return {"status": "custom_price", "price": price}
                        except ValueError:
                            self.send_message("⚠️ Please enter a valid number like <code>4.99</code>")

            time.sleep(2)

        self.send_message(
            f"⏰ <b>Approval timeout</b> — no response in 24 hours.\n"
            f"Run ID <code>{run_id}</code> has been cancelled."
        )
        return {"status": "timeout", "price": 0.0}

    def send_listing_confirmation(self, title: str, price: float, ebay_url: str) -> None:
        msg = (
            f"🎉 <b>Listed on eBay!</b>\n\n"
            f"<b>Title:</b> {title}\n"
            f"<b>Price:</b> ${price:.2f}\n"
            f"<b>Link:</b> <a href='{ebay_url}'>{ebay_url}</a>"
        )
        self.send_message(msg)

    def send_error_notification(self, run_id: str, error: str) -> None:
        msg = (
            f"⚠️ <b>Pipeline Error</b>\n\n"
            f"Run ID: <code>{run_id}</code>\n"
            f"Error: <code>{error[:500]}</code>"
        )
        self.send_message(msg)
