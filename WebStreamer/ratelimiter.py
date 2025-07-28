# This file is a part of TG-FileStreamBot

import time
from collections import defaultdict
from WebStreamer.vars import Var

class RateLimiter:
    """
    A simple in-memory rate limiter for users.
    """
    def __init__(self):
        self.user_requests = defaultdict(list)
        self.limit = Var.MAX_REQUESTS
        self.window = Var.TIME_WINDOW

    def is_limited(self, user_id: int) -> bool:
        """
        Checks if a user is rate-limited.

        Args:
            user_id (int): The user's Telegram ID.

        Returns:
            bool: True if the user has exceeded the request limit, False otherwise.
        """
        current_time = time.time()
        
        # Remove timestamps that are outside the current time window
        self.user_requests[user_id] = [
            timestamp for timestamp in self.user_requests[user_id] 
            if current_time - timestamp < self.window
        ]
        
        # Check if the number of requests within the window exceeds the limit
        if len(self.user_requests[user_id]) >= self.limit:
            return True  # User is rate-limited
            
        # If not limited, record the current request time and allow it
        self.user_requests[user_id].append(current_time)
        return False  # User is not rate-limited

