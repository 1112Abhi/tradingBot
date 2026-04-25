# telegram/listener.py - Telegram Command Listener (daemon thread)
#
# Runs as a background thread inside CandleWatcher.run().
# Polls Telegram for incoming messages and routes them to command handlers.
# Read-only access to DB — no writes, no contention with the watcher.

import logging
import threading
import time

import requests

import config
from telegram.commands import handle_command


class BotListener:
    """
    Polls Telegram getUpdates API and dispatches commands.
    Designed to run as a daemon thread alongside CandleWatcher.
    """

    def __init__(self, db) -> None:
        self.db      = db
        self.offset  = 0
        self._stop   = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> threading.Thread:
        """Start the listener as a background daemon thread. Returns the thread."""
        t = threading.Thread(target=self._loop, name="TelegramListener", daemon=True)
        t.start()
        logging.info("[LISTENER] Telegram command listener started")
        return t

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                updates = self._get_updates()
                for update in updates:
                    self.offset = update.get("update_id", 0) + 1
                    self._process(update)
            except Exception as exc:
                logging.warning(f"[LISTENER] Error in polling loop: {exc}")
            time.sleep(config.POLLING_INTERVAL)

    def _get_updates(self) -> list:
        resp = requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates",
            params={"offset": self.offset, "timeout": 10, "allowed_updates": ["message"]},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])

    def _process(self, update: dict) -> None:
        message = update.get("message", {})
        text    = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            return

        logging.info(f"[LISTENER] Received: {text!r}")

        try:
            reply = handle_command(text, self.db)
        except Exception as exc:
            logging.warning(f"[LISTENER] Command error: {exc}")
            reply = "⚠️ Something went wrong processing your command."

        self._send(chat_id, reply)

    def _send(self, chat_id: int, text: str) -> None:
        try:
            requests.post(
                f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=5,
            )
        except Exception as exc:
            logging.warning(f"[LISTENER] Failed to send reply: {exc}")
