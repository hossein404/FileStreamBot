# WebStreamer/server/security.py
import bcrypt
import secrets
from aiohttp import web

CSRF_SESSION_KEY = "csrf_token"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    if not plain_password or not hashed_password:
        return False
    try:
        # Ensure hashed_password is bytes
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)
    except (ValueError, TypeError):
        return False

async def generate_csrf_token(request: web.Request, new_token: bool = False) -> str:
    """
    Generates and stores a CSRF token in the application context.
    NOTE: Using app context as a session store is not suitable for multi-process or
    production environments. Consider aiohttp_session with a proper storage.
    """
    if 'session' not in request.app:
        request.app['session'] = {}

    if new_token or CSRF_SESSION_KEY not in request.app['session']:
        csrf_token = secrets.token_hex(32)
        request.app['session'][CSRF_SESSION_KEY] = csrf_token
    
    return request.app['session'][CSRF_SESSION_KEY]

async def validate_csrf_token(request: web.Request, received_token: str):
    """Validates the received CSRF token against the one in the session."""
    if 'session' not in request.app or CSRF_SESSION_KEY not in request.app['session']:
        raise web.HTTPForbidden(text="CSRF validation failed: No token in session.")
        
    expected_token = request.app['session'].get(CSRF_SESSION_KEY)
    
    if not received_token or not secrets.compare_digest(expected_token, received_token):
        raise web.HTTPForbidden(text="CSRF validation failed: Token mismatch.")