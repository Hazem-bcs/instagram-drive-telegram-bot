"""Securely install a dedicated fine-grained GitHub PAT into Cloudflare Workers.

This PAT should be scoped to Hazem-bcs/instagram-drive-telegram-bot with
Actions: Read and write. It is read by getpass, not shell history or source.
"""
import getpass
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "Hazem-bcs/instagram-drive-telegram-bot"
WORKFLOW_URL = f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/transfer.yml"


def wrangler_command():
    binary = shutil.which("wrangler")
    if binary:
        return [binary]
    candidates = list((Path.home() / ".npm" / "_npx").glob("*/node_modules/wrangler/bin/wrangler.js"))
    if candidates and shutil.which("node"):
        return [shutil.which("node"), str(max(candidates, key=lambda p: p.stat().st_mtime))]
    raise RuntimeError("Wrangler CLI not found; install it locally first.")


def main():
    print("GitHub fine-grained token setup")
    print(f"Grant access ONLY to {REPOSITORY}, permission Actions: Read and write.")
    token = getpass.getpass("Paste fine-grained GitHub token (hidden): ").strip()
    if not token:
        raise RuntimeError("Empty token.")
    request = Request(
        WORKFLOW_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "instagram-drive-telegram-bot-setup",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            workflow = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"GitHub verification failed (HTTP {error.code}).") from None
    except URLError:
        raise RuntimeError("Could not connect to GitHub API.") from None
    if workflow.get("path") != ".github/workflows/transfer.yml":
        raise RuntimeError("The token cannot access the expected workflow.")
    command = wrangler_command() + ["secret", "put", "GITHUB_TOKEN", "--name", "instagram-drive-telegram-bot"]
    result = subprocess.run(command, input=token + "\n", text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("Cloudflare secret installation failed. Check Wrangler login.")
    print("SUCCESS: GITHUB_TOKEN secret installed in Cloudflare Worker.")
    print("Warning: write permission was not exercised, so test a real bot request after Google OAuth setup.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
