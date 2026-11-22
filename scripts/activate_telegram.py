"""Interactive one-time Telegram activation; tokens never enter command-line arguments or git."""
from __future__ import annotations

import getpass
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

OWNER_REPO = "Hazem-bcs/instagram-drive-telegram-bot"
BOT_USERNAME = "hazemdownloaderbot"
WORKER_URL = "https://instagram-drive-telegram-bot.zad-market.workers.dev"


def api(token: str, method: str, payload: dict | None = None) -> dict:
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=25) as response:
            result = json.load(response)
    except Exception:
        raise RuntimeError(f"Telegram {method} failed; check connectivity/token.") from None
    if not result.get("ok"):
        raise RuntimeError(f"Telegram {method} rejected the request.")
    return result["result"]


def wrangler_cmd() -> list[str]:
    binary = shutil.which("wrangler")
    if binary:
        return [binary]
    candidates = list((Path.home() / ".npm" / "_npx").glob("*/node_modules/wrangler/bin/wrangler.js"))
    if not candidates or not shutil.which("node"):
        raise RuntimeError("Wrangler not found. Run npm install or npx wrangler first.")
    return [shutil.which("node"), str(max(candidates, key=lambda item: item.stat().st_mtime))]


def send_secret(command: list[str], secret: str, name: str) -> None:
    # Write the secret to the command's stdin, never in argv or shell history.
    result = subprocess.run(command, input=secret + "\n", text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Failed to configure {name}; check Cloudflare/GitHub login.")


def main() -> int:
    print(f"Activating @{BOT_USERNAME}. Send /start to the bot before proceeding.")
    token = getpass.getpass("Paste BotFather HTTP API token here (hidden): ").strip()
    if not token:
        raise RuntimeError("Empty Telegram bot token.")
    bot = api(token, "getMe")
    if bot.get("username", "").lower() != BOT_USERNAME:
        raise RuntimeError("Token does not belong to the expected bot.")
    updates = api(token, "getUpdates", {"limit": 100, "timeout": 0})
    users = sorted({
        (str(m["from"]["id"]), str(m["chat"]["id"]))
        for u in updates
        if (m := u.get("message"))
        and m.get("chat", {}).get("type") == "private"
        and m.get("from", {}).get("id")
    })
    if not users:
        raise RuntimeError("No private messages found. Send /start to your bot, then rerun.")
    for user_id, chat_id in users:
        print(f"Telegram user ID: {user_id} | Chat ID: {chat_id}")
    chosen = input("Enter YOUR Telegram user ID from the list above: ").strip()
    if (chosen, chosen) not in users:
        raise RuntimeError("That ID is not an eligible private chat.")
    if input(f"Authorize ONLY Telegram ID {chosen}? Type YES: ").strip() != "YES":
        raise RuntimeError("Canceled without configuring secrets.")
    root = Path(__file__).resolve().parent.parent
    setup = Path.home() / ".config" / "instagram-drive-telegram-bot"
    hook_secret = (setup / "TELEGRAM_WEBHOOK_SECRET").read_text().strip()
    if not hook_secret:
        raise RuntimeError("Webhook secret missing. Ask to regenerate it.")
    print("Installing GitHub and Cloudflare secrets...")
    send_secret(["gh", "secret", "set", "TELEGRAM_BOT_TOKEN", "-R", OWNER_REPO], token, "GitHub bot token")
    wrangler = wrangler_cmd()
    for key, value in (
        ("TELEGRAM_BOT_TOKEN", token),
        ("TELEGRAM_ALLOWED_USER_ID", chosen),
    ):
        send_secret(wrangler + ["secret", "put", key], value, f"Cloudflare {key}")
    api(token, "setWebhook", {
        "url": WORKER_URL + "/telegram",
        "secret_token": hook_secret,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    })
    print("Bot webhook registered. /start should now respond in Telegram.")
    print("Video transfers still require GITHUB_TOKEN (fine-grained) and GOOGLE_OAUTH_JSON.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
