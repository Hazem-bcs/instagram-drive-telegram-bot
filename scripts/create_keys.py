import secrets

print("PIPELINE_KEY (GitHub Actions secret AND Cloudflare secret):")
print(secrets.token_urlsafe(32))
print("\nTELEGRAM_WEBHOOK_SECRET (Cloudflare secret + local setup_webhook.py):")
print(secrets.token_urlsafe(32))
print("\nStore these securely. Never add them to the public repository.")
