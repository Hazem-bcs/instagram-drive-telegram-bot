"""Run once on your own computer. Do not send output credentials over chat."""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main():
    source = Path("client_secret.json")
    if not source.exists():
        raise SystemExit("Put OAuth Desktop client JSON in repo root as client_secret.json (gitignored).")
    flow = InstalledAppFlow.from_client_secrets_file(str(source), scopes=SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not credentials.refresh_token:
        raise SystemExit("Google did not issue a refresh token. Try revoking the app and consenting again.")
    target = Path(".secrets/google_oauth.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(credentials.to_json(), encoding="utf-8")
    target.chmod(0o600)
    print(f"Saved the OAuth credentials locally: {target}")
    print("Copy its full JSON content ONLY into the GitHub Actions secret GOOGLE_OAUTH_JSON.")
    print("Never commit this file or share it in chat.")


if __name__ == "__main__":
    main()
