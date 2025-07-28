# WebStreamer/errors.py

class InvalidHash(Exception):
    """Raised when the security hash is invalid."""
    message = "Invalid hash"

class FIleNotFound(Exception):
    """Raised when a file is not found in the database or channel."""
    message = "File not found"

class BannedUser(Exception):
    """Raised when a banned user tries to use the bot"""
    message = "You are banned"
