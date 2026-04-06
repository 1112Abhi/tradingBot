# telegram_bot.py - Telegram Messaging Module

import config
import requests


def send_message(text: str) -> bool:
    """
    Send a message to Telegram chat.

    Args:
        text: Message string to send.

    Returns:
        True on success, False on failure.
    """
    if not text or not isinstance(text, str):
        return False

    # Build API request
    url = f"{config.TELEGRAM_API_URL.replace('{token}', config.TELEGRAM_BOT_TOKEN)}"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[TELEGRAM] ✅ Message sent successfully")
            return True
        else:
            print(f"[TELEGRAM] ❌ Failed to send message: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[TELEGRAM] ❌ Request error: {e}")
        return False
