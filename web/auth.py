import os
import secrets
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse

DEFAULT_SECRET_KEY = os.environ.get("BOWLING_SECRET_KEY", "bowling2026")
SESSION_COOKIE_NAME = "bowling_auth_token"

# In-memory session store (valid until server restart)
ACTIVE_SESSIONS = set()

def verify_passcode(passcode: str) -> bool:
    expected = os.environ.get("BOWLING_SECRET_KEY", DEFAULT_SECRET_KEY)
    return secrets.compare_digest(passcode.strip(), expected.strip())

def create_session() -> str:
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS.add(token)
    return token

def revoke_session(token: str):
    ACTIVE_SESSIONS.discard(token)

def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token and token in ACTIVE_SESSIONS:
        return True
    return False

def require_auth(request: Request):
    """Dependency for API endpoints or HTML pages that require authentication."""
    if not is_authenticated(request):
        # If it's an API call, return 401
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        # If it's a page request, redirect to login
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
