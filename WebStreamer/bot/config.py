# WebStreamer/bot/config.py
import logging
from WebStreamer.vars import Var
from WebStreamer.bot.database import get_db_settings, update_db_setting

class Config:
    def __init__(self):
        # Default values from vars.py
        self.rate_limit = Var.RATE_LIMIT
        self.max_requests = Var.MAX_REQUESTS
        self.time_window = Var.TIME_WINDOW

    async def load_from_db(self):
        try:
            settings = await get_db_settings()
            self.rate_limit = settings.get('rate_limit', str(Var.RATE_LIMIT)).lower() == 'true'
            self.max_requests = int(settings.get('max_requests', Var.MAX_REQUESTS))
            self.time_window = int(settings.get('time_window', Var.TIME_WINDOW))
            logging.info("Configuration loaded from database.")
        except Exception as e:
            logging.error(f"Failed to load settings from DB: {e}. Using default values.")
    
    async def update_setting(self, key, value):
        if hasattr(self, key):
            # Convert to correct type before setting
            current_type = type(getattr(self, key))
            try:
                if current_type == bool:
                    setattr(self, key, str(value).lower() in ['true', '1', 't', 'y', 'yes'])
                else:
                    setattr(self, key, current_type(value))
                
                await update_db_setting(key, str(value))
                logging.info(f"Configuration updated: {key} = {value}")
            except ValueError:
                 logging.error(f"Invalid value type for config key '{key}'. Expected {current_type}.")
        else:
            logging.warning(f"Attempted to update non-existent config key: {key}")

# Singleton instance
config = Config()