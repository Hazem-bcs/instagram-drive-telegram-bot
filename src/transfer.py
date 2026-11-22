"""Secure ephemeral transfer: encrypted GitHub input -> Instagram -> Google Drive -> Telegram.

Expected environment: ENCRYPTED_PAYLOAD, PIPELINE_KEY, GOOGLE_OAUTH_JSON,
TELEGRAM_BOT_TOKEN.  The workflow never prints URLs or credentials.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
MAX_FILE_BYTES = 250 * 1024 * 1024


def decode_url_base64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decode_job(ciphertext: str, encoded_key: str) -> dict:
    key = decode_url_base64(encoded_key)
    if len(key) != 32:
        raise ValueError("Invalid encryption key")
    iv, encrypted = ciphertext.split(".", 1)
    data = AESGCM(key).decrypt(decode_url_base64(iv), decode_url_base64(encrypted), None)
    job = json.loads(data)
    if not isinstance(job, dict):
        raise ValueError("Job must be a JSON object")
    job_url = validate_instagram_url(job.get("url", ""))
    chat_id = str(job.get("chat_id", ""))
    if not re.fullmatch(r"\d{3,20}", chat_id):
        raise ValueError("Invalid Telegram chat ID")
    return {"url": job_url, "chat_id": chat_id}


def validate_instagram_url(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 2048:
        raise ValueError("Invalid Instagram URL")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or parsed.hostname not in ("instagram.com", "www.instagram.com", "m.instagram.com"):
        raise ValueError("URL must use Instagram HTTPS")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError("Unexpected URL components")
    match = re.fullmatch(r"/(reel|reels|p|tv)/([A-Za-z0-9_-]+)/?", parsed.path, flags=re.I)
    if not match:
        raise ValueError("Unsupported Instagram video URL")
    return f"https://www.instagram.com/{match.group(1).lower()}/{match.group(2)}/"


def telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError("Telegram notification failed")


def drive_service():
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials_json = json.loads(os.environ["GOOGLE_OAUTH_JSON"])
    creds = Credentials.from_authorized_user_info(credentials_json, scopes=DRIVE_SCOPES)
    if not creds.valid:
        creds.refresh(GoogleRequest())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def search_existing(service, parent_id: str, filename: str) -> dict | None:
    safe_name = filename.replace("\\", "\\\\").replace("'", "\\'")
    items = service.files().list(
        q=f"'{parent_id}' in parents and name = '{safe_name}' and trashed = false",
        fields="files(id,name,webViewLink),nextPageToken", pageSize=10,
    ).execute().get("files", [])
    return items[0] if items else None


def ensure_public(service, file_id: str) -> None:
    # Publishing the link is an explicit product requirement. The file is viewable by anyone with the link.
    permissions = service.permissions().list(fileId=file_id, fields="permissions(id,type,role)").execute().get("permissions", [])
    if not any(p.get("type") == "anyone" and p.get("role") == "reader" for p in permissions):
        service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()


def ensure_folder(service, name: str = "Instagram Videos") -> dict:
    safe = name.replace("\\", "\\\\").replace("'", "\\'")
    results = service.files().list(
        q=f"name = '{safe}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id,name,webViewLink),nextPageToken", pageSize=10,
    ).execute().get("files", [])
    if results:
        folder = results[0]
    else:
        folder = service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder"}, fields="id,name,webViewLink").execute()
    if os.getenv("PUBLIC_FOLDER", "true").lower() == "true":
        ensure_public(service, folder["id"])
    return folder


class QuietLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def get_first_video_info(info: dict) -> dict:
    if "entries" in info:
        entry = next((item for item in (info.get("entries") or []) if item), None)
        if not entry:
            raise ValueError("No downloadable video found")
        return entry
    return info


def download_video(url: str, directory: str) -> tuple[Path, str]:
    import yt_dlp

    options = {
        "outtmpl": str(Path(directory) / "instagram_%(id)s.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "playlist_items": "1",
        "max_filesize": MAX_FILE_BYTES,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "quiet": True,
        "no_warnings": True,
        "logger": QuietLogger(),
        "noprogress": True,
        "restrictfilenames": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
    if not info:
        raise ValueError("Unable to download Instagram video")
    entry = get_first_video_info(info)
    video_id = str(entry.get("id") or "unknown")
    video_id = re.sub(r"[^A-Za-z0-9_-]", "", video_id)[:100] or "unknown"
    paths = [p for p in Path(directory).iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not paths:
        raise ValueError("Downloaded file not found")
    file_path = max(paths, key=lambda p: p.stat().st_size)
    if file_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Video exceeds the 250 MB limit")
    return file_path, video_id


def upload_video(service, path: Path, filename: str, folder_id: str) -> dict:
    from googleapiclient.http import MediaFileUpload

    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True, chunksize=8 * 1024 * 1024)
    request = service.files().create(body={"name": filename, "parents": [folder_id]}, media_body=media, fields="id,webViewLink")
    result = None
    while result is None:
        _, result = request.next_chunk()
    ensure_public(service, result["id"])
    return result


def main() -> int:
    chat_id = None
    try:
        job = decode_job(os.environ["ENCRYPTED_PAYLOAD"], os.environ["PIPELINE_KEY"])
        chat_id = job["chat_id"]
        bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        service = drive_service()
        folder = ensure_folder(service, os.getenv("DRIVE_FOLDER_NAME", "Instagram Videos"))
        with tempfile.TemporaryDirectory() as directory:
            path, video_id = download_video(job["url"], directory)
            filename = f"Instagram_{video_id}{path.suffix.lower()}"
            found = search_existing(service, folder["id"], filename)
            result = found if found else upload_video(service, path, filename, folder["id"])
            ensure_public(service, result["id"])
        file_link = f"https://drive.google.com/file/d/{result['id']}/view"
        folder_link = f"https://drive.google.com/drive/folders/{folder['id']}"
        telegram_message(bot_token, chat_id, f"✅ تم حفظ الفيديو في Google Drive.\n🎬 {file_link}\n📁 المجلد: {folder_link}")
        print("Transfer completed successfully (sensitive URLs omitted).")
        return 0
    except Exception as exc:
        # Public GitHub Actions logs must not include the input URL or secrets.
        print(f"Transfer failed ({type(exc).__name__}); details intentionally omitted.", file=sys.stderr)
        if chat_id and os.getenv("TELEGRAM_BOT_TOKEN"):
            try:
                telegram_message(os.environ["TELEGRAM_BOT_TOKEN"], chat_id,
                                 "❌ تعذّر تنزيل الفيديو أو رفعه. قد يكون الرابط خاصاً أو يمنع Instagram التنزيل، أو توجد مشكلة في إعداد Google Drive.")
            except Exception:
                print("Could not deliver error notification.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
