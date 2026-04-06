# bot_listener.py - Telegram Bot Message Listener

import time
from typing import Optional

import requests

import config
from telegram.bot import send_message
from telegram.commands import handle_command


class BotListener:
    """Poll Telegram API for messages and handle commands."""

    def __init__(self):
        self.offset = 0
        self.api_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"

    def get_updates(self) -> list:
        """Fetch new messages from Telegram API."""
        try:
            params = {
                "offset": self.offset,
                "timeout": config.POLLING_TIMEOUT,
                "allowed_updates": ["message"],
            }
            response = requests.get(self.api_url, params=params, timeout=config.POLLING_TIMEOUT + 5)
            response.raise_for_status()
            return response.json().get("result", [])
        except requests.exceptions.RequestException as e:
            print(f"[LISTENER] API Error: {e}")
            return []

    def process_update(self, update: dict) -> None:
        """Handle a single message update."""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            return

        print(f"[LISTENER] Received: {text}")

        # Handle command
        response = handle_command(text)
        
        # Send response back
        self.send_response(chat_id, response)

    def send_response(self, chat_id: str, text: str) -> None:
        """Send response message to user."""
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                print(f"[LISTENER] Response sent ✅")
            else:
                print(f"[LISTENER] Response failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[LISTENER] Send Error: {e}")

    def run(self) -> None:
        """Start polling for messages (blocking)."""
        print("[LISTENER] Bot listener started. Waiting for messages...")
        
        try:
            while True:
                updates = self.get_updates()
                
                for update in updates:
                    self.offset = update.get("update_id", 0) + 1
                    self.process_update(update)
                
                time.sleep(config.POLLING_INTERVAL)
        except KeyboardInterrupt:
            print("\n[LISTENER] Bot stopped.")


def main():
    """Entry point for bot listener."""
    listener = BotListener()
    listener.run()


if __name__ == "__main__":
    main()
