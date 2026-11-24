# Interactive YouTube queue

The Telegram bot queues YouTube URLs in a private Cloudflare D1 database.
Other platforms continue using the existing GitHub workflow.

Use this only interactively, for videos you are authorized to download.
No background polling, automatic wake-up or keepalive is provided.
The worker API requires a separate bearer token, never a Telegram bot token.
Do not put any credentials in GitHub or send them in chat.

One-time setup in Google Cloud Shell:
1. Copy the private configuration file supplied by the owner to
   ~/.config/video-queue/config.json, with permissions 600.
2. Clone this repository and install requirements in a virtual environment:
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
3. Run .venv/bin/python src/cloudshell_queue.py --check to verify Drive access.

To process up to five waiting jobs when you open a session:
    .venv/bin/python src/cloudshell_queue.py

Use --limit 1 to process only the next job. Files are uploaded to the
existing Instagram Videos folder with the same link-sharing policy.
The bot sends the resulting Drive link. A disconnected job is reclaimable
after its one-hour lease. Failed transfers may be resubmitted in Telegram.
The default download is 360p MP4; existing files are reused.
