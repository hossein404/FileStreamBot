# WebStreamer/ratelimiter.py
import time
from collections import defaultdict
from WebStreamer.bot.config import config

class RateLimiter:
    """A simple in-memory rate limiter for users that uses live config."""
    def __init__(self):
        self.user_requests = defaultdict(list)

    @property
    def limit(self):
        return config.max_requests

    @property
    def window(self):
        return config.time_window

    def is_limited(self, user_id: int) -> bool:
        """Checks if a user is rate-limited."""
        current_time = time.time()
        
        self.user_requests[user_id] = [
            timestamp for timestamp in self.user_requests[user_id] 
            if current_time - timestamp < self.window
        ]
        
        if len(self.user_requests[user_id]) >= self.limit:
            return True
            
        self.user_requests[user_id].append(current_time)
        return False