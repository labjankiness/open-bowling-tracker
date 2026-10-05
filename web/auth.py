import os
import hmac
import hashlib
import secrets
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

DEFAULT_SECRET_KEY = os.environ.get("BOWLING_SECRET_KEY", "bowling2026")
SESSION_COOKIE_NAME = "bowling_auth_token"

def _get_signing_key() -> bytes:
    key = os.environ.get("BOWLING_SECRET_KEY", DEFAULT_SECRET_KEY).strip()
    return key.encode("utf-8")

def verify_passcode(passcode: str) -> bool:
    expected = os.environ.get("BOWLING_SECRET_KEY", DEFAULT_SECRET_KEY)
    return secrets.compare_digest(passcode.strip(), expected.strip())

def create_session() -> str:
    """Creates a persistent HMAC token based on the secret key so sessions survive server reloads."""
    return hmac.new(_get_signing_key(), b"bowling_authenticated_session", hashlib.sha256).hexdigest()

def revoke_session(token: str):
    pass

def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    expected = hmac.new(_get_signing_key(), b"bowling_authenticated_session", hashlib.sha256).hexdigest()
    return secrets.compare_digest(token, expected)

def require_auth(request: Request):
    if not is_authenticated(request):
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
