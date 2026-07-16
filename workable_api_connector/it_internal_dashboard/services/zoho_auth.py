"""
zoho_auth.py
------------
Stateless helper for OAuth URL construction and one-time code exchange.
Runs ONCE during initial setup. After that, the credentials model
handles token refresh automatically.

IMPORTANT: ZOHO_AUTH_BASE must always be the full absolute URL
including the https:// scheme. A relative path here causes Odoo's
request.redirect() to prepend localhost instead of going to Zoho.
"""
import urllib.parse
import requests

# Full absolute URL — never a relative path
ZOHO_AUTH_BASE = "https://accounts.zoho.com/oauth/v2"
ZOHO_TOKEN_URL = f"{ZOHO_AUTH_BASE}/token"

DEFAULT_SCOPES = ",".join([
    "Desk.tickets.READ",
    "Desk.search.READ",
    "Desk.basic.READ",
    "ZohoAnalytics.fullaccess.all",
])


def build_auth_url(client_id: str, redirect_uri: str) -> str:
    """
    Build the full Zoho OAuth authorization URL.
    The returned string MUST start with https://accounts.zoho.com
    or Odoo will treat it as a local path and redirect to localhost.
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": DEFAULT_SCOPES,
        "redirect_uri": redirect_uri,
        "access_type": "offline",   # required to receive a refresh token
        "prompt": "consent",        # forces Zoho to always show approval screen
    }

    query_string = urllib.parse.urlencode(params)
    full_url = f"{ZOHO_AUTH_BASE}/auth?{query_string}"

    # Hard guard — if this ever fires, the constant above is wrong
    if not full_url.startswith("https://accounts.zoho.com"):
        raise ValueError(
            f"Auth URL is not pointing to Zoho. Got: {full_url[:100]}\n"
            "Check ZOHO_AUTH_BASE in services/zoho_auth.py."
        )

    return full_url


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict:
    """
    Exchange the one-time authorization code Zoho sent to the callback URL
    for an access token and a refresh token.

    Called exactly once per OAuth setup. After this, token refresh is
    handled automatically by it.zoho.credentials.get_valid_access_token().
    """
    response = requests.post(
        ZOHO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise ValueError(
            f"Zoho token exchange failed: {data['error']}\n"
            "Common causes: code already used, redirect_uri mismatch, "
            "wrong client_secret."
        )

    if "refresh_token" not in data:
        raise ValueError(
            "Zoho did not return a refresh token. "
            "Make sure access_type=offline was in the auth URL "
            "and the user clicked Accept (not just Skip)."
        )

    return data