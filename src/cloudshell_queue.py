"""Manually invoked, finite YouTube batch; no daemon, polling or keepalive."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from transfer import (
    drive_service, search_existing, upload_video, ensure_public, download_video,
    safe_error_category,
)
from media_urls import parse_video_url

ENDPOINT = "https://instagram-drive-telegram-bot.zad-market.workers.dev"
FOLDER_ID = "1Qtiep0tseA8H38eV4n65is4p2GszNXcV"
CONFIG = Path.home() / ".config" / "video-queue" / "config.json"


def request_queue(config, action, body=None):
    request = Request(f"{ENDPOINT}/youtube/{action}",
                      data=json.dumps(body or {}).encode(),
                      headers={"Authorization": "Bearer " + config["queue_token"],
                               "Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--check", action="store_true", help="check Drive authorization only")
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be 1 to 20")
    if not CONFIG.is_file() or CONFIG.stat().st_mode & 0o077:
        print("Missing private config or permissions too broad. Use chmod 600 on config.json.")
        return 1
    try:
        config = json.loads(CONFIG.read_text())
        os.environ["GOOGLE_OAUTH_JSON"] = json.dumps(config["google_oauth"])
        service = drive_service()
        folder = service.files().get(fileId=FOLDER_ID, fields="id,mimeType,capabilities(canAddChildren)").execute()
        if folder.get("mimeType") != "application/vnd.google-apps.folder" or not folder.get("capabilities", {}).get("canAddChildren"):
            raise RuntimeError("Drive folder is not writable")
    except Exception as exc:
        print("Drive configuration check failed:", type(exc).__name__)
        return 1
    print("DRIVE_READY", flush=True)
    if args.check:
        return 0
    failed = False
    for _ in range(args.limit):
        try:
            job = request_queue(config, "claim")["job"]
        except Exception as exc:
            print("Queue unavailable:", type(exc).__name__)
            return 1
        if not job:
            print("Queue empty.")
            break
        receipt = {"id": job["id"], "lease_token": job["lease_token"]}
        try:
            url, platform = parse_video_url(job["url"])
            if platform != "YouTube":
                raise ValueError("Unexpected platform")
            video_id = url.split("v=", 1)[1]
            filename = f"YouTube_{video_id}.mp4"
            result = search_existing(service, FOLDER_ID, filename)
            if not result:
                with tempfile.TemporaryDirectory() as directory:
                    file, downloaded_id = download_video(
                        url, directory,
                        "bv[ext=mp4][height<=360]+ba[ext=m4a]/b[ext=mp4][height<=360]",
                    )
                    if file.suffix.lower() != ".mp4" or downloaded_id != video_id:
                        raise ValueError("Unexpected media output")
                    result = upload_video(service, file, filename, FOLDER_ID)
            ensure_public(service, result["id"])
            receipt["file_id"] = result["id"]
        except Exception as exc:
            failed = True
            print("Transfer failed:", safe_error_category(exc), flush=True)
            receipt["failed"] = True
        try:
            request_queue(config, "finish", receipt)
            if "file_id" in receipt:
                print("Saved to Drive; Telegram notified.", flush=True)
        except Exception as exc:
            print("Completion notification failed; job can be recovered after lease expiry:", type(exc).__name__)
            return 1
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
