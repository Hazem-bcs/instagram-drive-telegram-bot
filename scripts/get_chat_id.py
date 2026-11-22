"""After sending /start to your bot, print your private Telegram user ID."""
import json
import os
from urllib.request import urlopen


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN environment variable locally.")
    with urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as response:
        data = json.load(response)
    if not data.get("ok"):
        raise SystemExit("Telegram API failed. If webhook already exists, remove it before getUpdates.")
    users = set()
    for update in data.get("result", []):
        message = update.get("message") or {}
        if message.get("chat", {}).get("type") == "private" and message.get("from"):
            users.add((message["from"]["id"], message["chat"]["id"]))
    if not users:
        print("Send /start to your bot on Telegram, then run this script again.")
    else:
        for user_id, chat_id in sorted(users):
            print(f"Telegram user ID: {user_id} | private chat ID: {chat_id}")


if __name__ == "__main__":
    main()
