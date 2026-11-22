"""Register HTTPS Cloudflare Worker webhook (using local environment variables)."""
import json
import os
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/set_webhook.py https://YOUR-WORKER.workers.dev")
    base = sys.argv[1].rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit("Pass a valid HTTPS Worker URL")
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    webhook_secret = os.environ["TELEGRAM_WEBHOOK_SECRET"]
    payload = json.dumps({
        "url": base + "/telegram",
        "secret_token": webhook_secret,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }).encode()
    endpoint = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    req = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=25) as response:
        data = json.load(response)
    if not data.get("ok"):
        raise SystemExit("Webhook registration failed")
    print("Webhook registered successfully. Now send /start to your Telegram bot.")


if __name__ == "__main__":
    main()
