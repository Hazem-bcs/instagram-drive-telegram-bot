"""Finish Telegram webhook registration without repeating the other secrets.

Run locally on the owner's machine. The token is entered securely with getpass,
is never persisted or placed in shell history, and is never printed.
"""
from __future__ import annotations

import getpass
import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BOT_NAME = "hazemdownloaderbot"
WORKER_URL = "https://instagram-drive-telegram-bot.zad-market.workers.dev/telegram"
SECRET_FILE = Path.home() / ".config/instagram-drive-telegram-bot/TELEGRAM_WEBHOOK_SECRET"


def telegram(token: str, method: str, payload: dict | None = None):
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    for attempt in range(1, 5):
        try:
            with urlopen(request, timeout=24) as response:
                result = json.load(response)
            if not result.get("ok"):
                raise RuntimeError(f"Telegram {method} returned ok=false: {result.get('description', 'unknown')}")
            return result["result"]
        except HTTPError as exc:
            try:
                error = json.loads(exc.read())
                reason = error.get("description", "unknown error")
            except (ValueError, OSError):
                reason = "unknown error"
            # Telegram's description does not contain the bot token.
            raise RuntimeError(f"Telegram {method} HTTP {exc.code}: {reason}") from None
        except (URLError, OSError, TimeoutError, ValueError) as exc:
            print(f"Network error ({type(exc).__name__}), attempt {attempt}/4", flush=True)
            if attempt == 4:
                raise RuntimeError("Telegram API is temporarily unreachable. Try again later.") from None
            time.sleep(attempt * 2)
    raise RuntimeError("Failed unexpectedly")


def main():
    if not SECRET_FILE.is_file():
        raise RuntimeError("Webhook secret missing from ~/.config/instagram-drive-telegram-bot/")
    secret = SECRET_FILE.read_text().strip()
    if not secret:
        raise RuntimeError("Webhook secret is empty.")
    token = getpass.getpass("Paste BotFather API token (hidden): ").strip()
    if not token:
        raise RuntimeError("Telegram token cannot be empty.")
    me = telegram(token, "getMe")
    if me.get("username", "").lower() != BOT_NAME:
        raise RuntimeError(f"This token does not belong to @{BOT_NAME}.")
    print("Verified bot. Registering webhook...")
    telegram(token, "setWebhook", {
        "url": WORKER_URL,
        "secret_token": secret,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    })
    info = telegram(token, "getWebhookInfo")
    if info.get("url") != WORKER_URL:
        raise RuntimeError("Telegram did not retain the expected webhook URL.")
    print("SUCCESS: Telegram webhook registered and verified.")
    print(f"Webhook URL: {WORKER_URL}")
    if info.get("last_error_message"):
        print("Note: Telegram reports a past delivery issue; test /start now.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
