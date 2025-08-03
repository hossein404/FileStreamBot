import bcrypt
import secrets
from aiohttp import web
from aiohttp_session import Session

CSRF_SESSION_KEY = "csrf_token"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    if not plain_password or not hashed_password:
        return False
    try:
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)
    except (ValueError, TypeError):
        return False

def generate_csrf_token(session: Session, new_token: bool = False) -> None:
    """
    Ensures a CSRF token exists in the session.
    Generates one if it's missing or if `new_token` is True.
    """
    if new_token or CSRF_SESSION_KEY not in session:
        session[CSRF_SESSION_KEY] = secrets.token_hex(32)

def validate_csrf_token(session: Session, received_token: str):
    """
    Validates the received CSRF token against the one stored in the session.
    Raises an HTTPForbidden error if validation fails.
    """
    expected_token = session.get(CSRF_SESSION_KEY)
    
    if not expected_token or not received_token or not secrets.compare_digest(expected_token, received_token):
        raise web.HTTPForbidden(text="CSRF validation failed: Token mismatch. Please try again.")