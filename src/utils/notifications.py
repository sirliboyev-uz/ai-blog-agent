"""Notification utilities for Telegram and Slack."""

import requests
from typing import Optional
from loguru import logger

from src.models.config import get_settings


class NotificationService:
    """Send notifications via Telegram or Slack."""

    def __init__(self):
        """Initialize notification service."""
        self.settings = get_settings()

    def send_success(self, site: str, post_title: str, post_url: str):
        """Send success notification."""
        message = f"""✅ Post Published Successfully

Site: {site}
Title: {post_title}
URL: {post_url}"""

        self._send(message)

    def send_failure(self, site: str, topic: str, error: str):
        """Send failure notification."""
        message = f"""❌ Post Generation Failed

Site: {site}
Topic: {topic}
Error: {error}"""

        self._send(message)

    def send_batch_summary(self, stats: dict):
        """Send batch processing summary."""
        message = f"""📊 Batch Processing Complete

Total: {stats['total']}
✅ Success: {stats['success']}
❌ Failed: {stats['failed']}"""

        self._send(message)

    def _send(self, message: str):
        """Send message to configured channels."""
        # Try Telegram
        if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
            self._send_telegram(message)

        # Try Slack
        if self.settings.slack_webhook_url:
            self._send_slack(message)

    def _send_telegram(self, message: str):
        """Send Telegram notification."""
        try:
            url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.settings.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            logger.debug("Telegram notification sent")

        except Exception as e:
            logger.warning(f"Failed to send Telegram notification: {e}")

    def _send_slack(self, message: str):
        """Send Slack notification."""
        try:
            payload = {"text": message}

            response = requests.post(
                self.settings.slack_webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            logger.debug("Slack notification sent")

        except Exception as e:
            logger.warning(f"Failed to send Slack notification: {e}")
