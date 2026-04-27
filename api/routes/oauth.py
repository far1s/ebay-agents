"""
/api/oauth/callback — Etsy OAuth redirect handler.
Etsy redirects here with ?code=XXX after the user approves the app.
The page displays the code so the user can copy-paste it into the setup script.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code", "")
    error = request.query_params.get("error", "")
    state = request.query_params.get("state", "")

    if error:
        html = f"""<!DOCTYPE html>
<html><head><title>Etsy OAuth Error</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:60px auto;text-align:center">
  <h2 style="color:#c0392b">Authorization Failed</h2>
  <p style="color:#555">Etsy returned an error: <code style="background:#fee;padding:4px 8px;border-radius:4px">{error}</code></p>
  <p>Close this tab and try again.</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)

    if not code:
        html = """<!DOCTYPE html>
<html><head><title>Etsy OAuth</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:60px auto;text-align:center">
  <h2 style="color:#c0392b">No Code Received</h2>
  <p style="color:#555">No authorization code was returned by Etsy. Try the flow again.</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)

    html = f"""<!DOCTYPE html>
<html><head>
  <title>Etsy Authorization Successful</title>
  <script>
    function copyCode() {{
      navigator.clipboard.writeText("{code}").then(() => {{
        document.getElementById('btn').textContent = 'Copied!';
        document.getElementById('btn').style.background = '#2a7d4f';
        setTimeout(() => {{
          document.getElementById('btn').textContent = 'Copy Code';
          document.getElementById('btn').style.background = '#f1641e';
        }}, 2000);
      }});
    }}
  </script>
</head>
<body style="font-family:sans-serif;max-width:600px;margin:60px auto;text-align:center;color:#333">
  <div style="background:#f0faf4;border:2px solid #2a7d4f;border-radius:12px;padding:40px">
    <h2 style="color:#2a7d4f;margin-top:0">Authorization Successful!</h2>
    <p style="color:#555;margin-bottom:24px">
      Copy the code below and paste it into the terminal running <code>etsy_oauth.py</code>
    </p>
    <div style="background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;word-break:break-all;font-family:monospace;font-size:13px;margin-bottom:20px;text-align:left">
      {code}
    </div>
    <button id="btn" onclick="copyCode()"
      style="background:#f1641e;color:#fff;border:none;padding:12px 32px;border-radius:8px;font-size:16px;cursor:pointer;font-weight:bold">
      Copy Code
    </button>
    <p style="color:#888;font-size:13px;margin-top:24px">
      This code expires in a few minutes. Return to the terminal after copying.
    </p>
  </div>
</body></html>"""
    return HTMLResponse(html)
