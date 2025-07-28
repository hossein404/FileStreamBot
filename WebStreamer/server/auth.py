# WebStreamer/server/auth.py
import bcrypt
import secrets
from aiohttp import web

CSRF_SESSION_KEY = "csrf_token"

def get_password_hash(password: str) -> str:
    """Hashes the password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except (ValueError, TypeError):
        return False

async def generate_csrf_token(request: web.Request, new_token: bool = False) -> str:
    """
    Generates and stores a CSRF token in the application context (acting as a temporary session).
    In a real application, this should be stored in a proper session (e.g., aiohttp_session).
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
    
    if not secrets.compare_digest(expected_token, received_token or ''):
        raise web.HTTPForbidden(text="CSRF validation failed: Token mismatch.")