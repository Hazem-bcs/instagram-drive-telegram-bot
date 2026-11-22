"""Authorize Google Drive with a user-owned Desktop OAuth client and store GitHub secret.

The client JSON must be downloaded from Google Cloud. This script detects a
recently downloaded Desktop client file, launches Google's consent page,
and stores the OAuth credentials in local private storage and GitHub Actions
secrets. It never prints credentials or uploads them to repository code.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
REPOSITORY = "Hazem-bcs/instagram-drive-telegram-bot"


def locate_client() -> Path:
    saved = Path("client_secret.json")
    if saved.exists():
        return saved
    downloads = Path.home() / "Downloads"
    candidates = sorted(
        downloads.glob("client_secret*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) if downloads.is_dir() else []
    for candidate in candidates:
        try:
            content = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(content, dict) and "installed" in content:
            shutil.copyfile(candidate, saved)
            saved.chmod(0o600)
            print("Found Google OAuth Desktop client downloaded to Downloads.")
            return saved
    raise RuntimeError(
        "Download OAuth Client ID JSON for Desktop app from Google Cloud. "
        "Keep its filename (client_secret*.json) in ~/Downloads and run this again."
    )


def main() -> None:
    source = locate_client()
    flow = InstalledAppFlow.from_client_secrets_file(str(source), scopes=SCOPES)
    print("Opening Google sign-in and consent page in your browser...")
    credentials = flow.run_local_server(
        host="localhost", port=0, open_browser=True,
        access_type="offline", prompt="consent",
    )
    if not credentials.refresh_token:
        raise RuntimeError("Google did not issue a refresh token. Try consenting again.")
    target = Path(".secrets/google_oauth.json")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    target.write_text(credentials.to_json(), encoding="utf-8")
    target.chmod(0o600)
    print("Google OAuth credentials stored locally (private).")
    result = subprocess.run(
        ["gh", "secret", "set", "GOOGLE_OAUTH_JSON", "-R", REPOSITORY],
        input=credentials.to_json(),
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(
            "Google consent completed, but GitHub secret upload failed. "
            "OAuth credentials are saved in .secrets/google_oauth.json."
        )
    print("SUCCESS: GOOGLE_OAUTH_JSON configured in GitHub Actions secrets.")
    print("No client secret or Google token was committed to the public repository.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        raise SystemExit(f"FAILED: {exc}") from None
