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
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

try:
    import httpx
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

REDIRECT_URI = "http://localhost:3003/callback"
SCOPES = "listings_r listings_w listings_d shops_r"
AUTH_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
ETSY_BASE = "https://openapi.etsy.com/v3"

_callback_data: dict = {}
_server_done = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _callback_data["code"] = params.get("code", [""])[0]
        _callback_data["state"] = params.get("state", [""])[0]
        _callback_data["error"] = params.get("error", [""])[0]

        body = b"""
        <html><body style="font-family:sans-serif;text-align:center;margin-top:80px">
        <h2 style="color:#2a7d4f">Authorization successful!</h2>
        <p>You can close this tab and return to the terminal.</p>
        </body></html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
        _server_done.set()

    def log_message(self, *args):
        pass  # Suppress default HTTP logs


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
        print(f"\n[ERROR] Token exchange failed {resp.status_code}: {resp.text}")
        sys.exit(1)
    return resp.json()


def _get_shop_id(api_key: str, access_token: str) -> str:
    headers = {
        "x-api-key": api_key,
        "Authorization": f"Bearer {access_token}",
    }
    # Get user ID
    me = httpx.get(f"{ETSY_BASE}/application/users/me", headers=headers, timeout=15)
    if me.status_code != 200:
        print(f"[WARN] Could not fetch user info ({me.status_code}). Shop ID must be set manually.")
        return ""
    user_id = me.json().get("user_id", "")
    if not user_id:
        return ""

    # Get shop
    shops = httpx.get(f"{ETSY_BASE}/application/users/{user_id}/shops", headers=headers, timeout=15)
    if shops.status_code != 200:
        print(f"[WARN] Could not fetch shop info ({shops.status_code}). Shop ID must be set manually.")
        return ""

    data = shops.json()
    # Response is either a shop object directly or a paginated list
    if "shop_id" in data:
        return str(data["shop_id"])
    results = data.get("results", [])
    if results:
        return str(results[0].get("shop_id", ""))
    return ""


def _update_vercel_env(key: str, value: str) -> bool:
    """Remove existing then add new value. Returns True on success."""
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
    print("BEFORE running this script you must:")
    print()
    print("  1. Go to: https://www.etsy.com/developers/register")
    print("  2. Click 'Register as a developer' (uses your existing Etsy login)")
    print("  3. Click 'Create a New App'")
    print("  4. Fill in:")
    print("       App Name: EtsyAgents (or anything)")
    print("       Description: Automated digital product listing")
    print("       Callback URL: http://localhost:3003/callback")
    print("  5. Submit → copy the 'Keystring' (API Key)")
    print()
    print("-" * 60)

    api_key = input("Paste your Etsy API Key (Keystring): ").strip()
    if not api_key:
        print("[ERROR] No API key entered. Exiting.")
        sys.exit(1)

    # PKCE
    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    # Build auth URL
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

    # Start local callback server
    server = HTTPServer(("localhost", 3003), _CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    print()
    print("Opening browser for Etsy authorization...")
    print(f"URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)
    print()
    print("Waiting for you to approve the app in the browser...")

    _server_done.wait(timeout=120)
    server.shutdown()

    if _callback_data.get("error"):
        print(f"\n[ERROR] Etsy returned error: {_callback_data['error']}")
        sys.exit(1)

    code = _callback_data.get("code")
    if not code:
        print("\n[ERROR] No authorization code received. Did you approve the app?")
        sys.exit(1)

    print("Authorization code received. Exchanging for tokens...")
    token_data = _exchange_code(api_key, code, verifier)

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token:
        print(f"\n[ERROR] No access token in response: {token_data}")
        sys.exit(1)

    print(f"Access token obtained (expires in {expires_in}s / 1 hour)")

    print("Fetching your Etsy shop ID...")
    shop_id = _get_shop_id(api_key, access_token)
    if shop_id:
        print(f"Shop ID found: {shop_id}")
    else:
        shop_id = input("Could not auto-detect shop ID. Enter it manually: ").strip()

    print()
    print("=" * 60)
    print("  SUCCESS! Your credentials:")
    print("=" * 60)
    print(f"  ETSY_API_KEY      = {api_key}")
    print(f"  ETSY_SHOP_ID      = {shop_id}")
    print(f"  ETSY_ACCESS_TOKEN = {access_token[:40]}...  (truncated)")
    if refresh_token:
        print(f"  ETSY_REFRESH_TOKEN= {refresh_token[:40]}...  (truncated)")
    print()

    # Save to local .env for dev use
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            env_lines = f.readlines()

    def _upsert_env(lines: list[str], key: str, value: str) -> list[str]:
        prefix = f"{key}="
        replaced = False
        new_lines = []
        for line in lines:
            if line.startswith(prefix):
                new_lines.append(f"{prefix}{value}\n")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f"{prefix}{value}\n")
        return new_lines

    env_lines = _upsert_env(env_lines, "ETSY_API_KEY", api_key)
    env_lines = _upsert_env(env_lines, "ETSY_SHOP_ID", shop_id)
    env_lines = _upsert_env(env_lines, "ETSY_ACCESS_TOKEN", access_token)
    if refresh_token:
        env_lines = _upsert_env(env_lines, "ETSY_REFRESH_TOKEN", refresh_token)

    with open(env_path, "w") as f:
        f.writelines(env_lines)
    print(f"  Saved to .env")

    # Offer to push to Vercel
    push = input("Push to Vercel now? (y/n): ").strip().lower()
    if push == "y":
        print()
        print("Updating Vercel environment variables...")
        vars_to_push = {
            "ETSY_API_KEY": api_key,
            "ETSY_SHOP_ID": shop_id,
            "ETSY_ACCESS_TOKEN": access_token,
        }
        if refresh_token:
            vars_to_push["ETSY_REFRESH_TOKEN"] = refresh_token

        all_ok = True
        for key, value in vars_to_push.items():
            ok = _update_vercel_env(key, value)
            print(f"  {'OK' if ok else 'FAIL'}  {key}")
            if not ok:
                all_ok = False

        if all_ok:
            print()
            print("All Vercel env vars updated.")
            redeploy = input("Redeploy to production now? (y/n): ").strip().lower()
            if redeploy == "y":
                subprocess.run(["vercel", "--prod", "--yes"])
        else:
            print("\nSome vars failed. Set them manually in the Vercel dashboard.")
    else:
        print()
        print("Skipped Vercel push. Set these manually in the Vercel dashboard or re-run this script.")

    print()
    print("Done! Your EtsyAgents system is ready to use.")


if __name__ == "__main__":
    main()
