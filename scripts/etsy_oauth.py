"""
Etsy OAuth 2.0 Setup Script
============================
Run this once to get your ETSY_API_KEY, ETSY_SHOP_ID, ETSY_ACCESS_TOKEN,
and ETSY_REFRESH_TOKEN, then optionally push them to Vercel automatically.

Usage:
    python scripts/etsy_oauth.py
"""
import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import webbrowser
from urllib.parse import urlencode

try:
    import httpx
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

REDIRECT_URI = "https://etsy-agents.vercel.app/api/oauth/callback"
SCOPES = "listings_r listings_w listings_d shops_r"
AUTH_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
ETSY_BASE = "https://openapi.etsy.com/v3"


def _generate_pkce() -> tuple[str, str]:
    raw = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _exchange_code(api_key: str, code: str, verifier: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": api_key,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"\n[ERROR] Token exchange failed {resp.status_code}:")
        print(resp.text)
        sys.exit(1)
    return resp.json()


def _get_shop_id(api_key: str, access_token: str) -> str:
    headers = {
        "x-api-key": api_key,
        "Authorization": f"Bearer {access_token}",
    }
    me = httpx.get(f"{ETSY_BASE}/application/users/me", headers=headers, timeout=15)
    if me.status_code != 200:
        print(f"[WARN] Could not fetch user info ({me.status_code}). You'll enter shop ID manually.")
        return ""
    user_id = me.json().get("user_id", "")
    if not user_id:
        return ""

    shops = httpx.get(f"{ETSY_BASE}/application/users/{user_id}/shops", headers=headers, timeout=15)
    if shops.status_code != 200:
        print(f"[WARN] Could not fetch shop info ({shops.status_code}). You'll enter shop ID manually.")
        return ""

    data = shops.json()
    if "shop_id" in data:
        return str(data["shop_id"])
    results = data.get("results", [])
    if results:
        return str(results[0].get("shop_id", ""))
    return ""


def _update_vercel_env(key: str, value: str) -> bool:
    try:
        subprocess.run(
            ["vercel", "env", "rm", key, "production", "--yes"],
            capture_output=True, timeout=30,
        )
        result = subprocess.run(
            ["vercel", "env", "add", key, "production"],
            input=value.encode(),
            capture_output=True, timeout=30,
        )
        return result.returncode == 0
    except Exception as exc:
        print(f"  [WARN] Could not update Vercel for {key}: {exc}")
        return False


def main():
    print("=" * 60)
    print("  Etsy OAuth 2.0 Setup")
    print("=" * 60)
    print()
    print("BEFORE running this script you must have already:")
    print()
    print("  1. Gone to: https://www.etsy.com/developers/your-apps")
    print("  2. Created a new app (any name — no 'Etsy' in the name)")
    print("  3. Set the callback URL to exactly:")
    print()
    print(f"       {REDIRECT_URI}")
    print()
    print("  4. Copied your Keystring (API Key)")
    print()
    print("-" * 60)

    api_key = input("Paste your Etsy API Key (Keystring): ").strip()
    if not api_key:
        print("[ERROR] No API key entered.")
        sys.exit(1)

    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "client_id": api_key,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print()
    print("Opening browser — approve the app on Etsy, then you'll be")
    print(f"redirected to your Vercel site which will show you a code.")
    print()
    webbrowser.open(auth_url)

    print("After approving on Etsy, the page will show you an authorization code.")
    print()
    code = input("Paste the authorization code here: ").strip()
    if not code:
        print("[ERROR] No code entered.")
        sys.exit(1)

    print()
    print("Exchanging code for access token...")
    token_data = _exchange_code(api_key, code, verifier)

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token:
        print(f"[ERROR] No access token returned: {token_data}")
        sys.exit(1)

    print(f"Access token obtained (expires in {expires_in}s)")

    print("Fetching your Etsy shop ID...")
    shop_id = _get_shop_id(api_key, access_token)
    if shop_id:
        print(f"Shop ID: {shop_id}")
    else:
        shop_id = input("Enter your Etsy Shop ID manually: ").strip()

    print()
    print("=" * 60)
    print("  Your credentials:")
    print("=" * 60)
    print(f"  ETSY_API_KEY       = {api_key}")
    print(f"  ETSY_SHOP_ID       = {shop_id}")
    print(f"  ETSY_ACCESS_TOKEN  = {access_token[:50]}...")
    if refresh_token:
        print(f"  ETSY_REFRESH_TOKEN = {refresh_token[:50]}...")
    print()

    # Save to local .env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8-sig") as f:
            env_lines = f.readlines()

    def _upsert(lines: list[str], key: str, value: str) -> list[str]:
        prefix = f"{key}="
        new_lines, replaced = [], False
        for line in lines:
            if line.startswith(prefix):
                new_lines.append(f"{prefix}{value}\n")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f"{prefix}{value}\n")
        return new_lines

    env_lines = _upsert(env_lines, "ETSY_API_KEY", api_key)
    env_lines = _upsert(env_lines, "ETSY_SHOP_ID", shop_id)
    env_lines = _upsert(env_lines, "ETSY_ACCESS_TOKEN", access_token)
    if refresh_token:
        env_lines = _upsert(env_lines, "ETSY_REFRESH_TOKEN", refresh_token)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(env_lines)
    print("  Saved to .env")

    push = input("Push to Vercel and redeploy? (y/n): ").strip().lower()
    if push != "y":
        print("\nDone. Set the env vars in the Vercel dashboard manually when ready.")
        return

    print()
    print("Updating Vercel environment variables...")
    vars_to_push: dict[str, str] = {
        "ETSY_API_KEY": api_key,
        "ETSY_SHOP_ID": shop_id,
        "ETSY_ACCESS_TOKEN": access_token,
    }
    if refresh_token:
        vars_to_push["ETSY_REFRESH_TOKEN"] = refresh_token

    all_ok = True
    for key, value in vars_to_push.items():
        ok = _update_vercel_env(key, value)
        print(f"  {'OK  ' if ok else 'FAIL'} {key}")
        if not ok:
            all_ok = False

    if all_ok:
        print()
        subprocess.run(["vercel", "--prod", "--yes"])
    else:
        print("\nSome vars failed. Set them manually in the Vercel dashboard.")

    print("\nDone! Your EtsyAgents system is configured and ready.")


if __name__ == "__main__":
    main()
