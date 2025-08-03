# WebStreamer/bot/config.py
import logging
from WebStreamer.vars import Var
from WebStreamer.bot.database import get_db_settings, update_db_setting

class Config:
    def __init__(self):
        self.rate_limit = Var.RATE_LIMIT
        self.max_requests = Var.MAX_REQUESTS
        self.time_window = Var.TIME_WINDOW
        self.force_sub_channel = 0 

    async def load_from_db(self):
        try:
            settings = await get_db_settings()
            self.rate_limit = settings.get('rate_limit', str(Var.RATE_LIMIT)).lower() == 'true'
            self.max_requests = int(settings.get('max_requests', Var.MAX_REQUESTS))
            self.time_window = int(settings.get('time_window', Var.TIME_WINDOW))
            fsc_value = settings.get('force_sub_channel', '0')
            self.force_sub_channel = fsc_value if fsc_value.startswith('@') else int(fsc_value)
            
            logging.info("Configuration loaded from database.")
        except Exception as e:
            logging.error(f"Failed to load settings from DB: {e}. Using default values.")
    
    async def update_setting(self, key, value):
        if hasattr(self, key):
            current_type = type(getattr(self, key))
            try:
                if key == 'force_sub_channel':
                    new_value = value if isinstance(value, str) and value.startswith('@') else int(value)
                    setattr(self, key, new_value)
                elif current_type == bool:
                    setattr(self, key, str(value).lower() in ['true', '1', 't', 'y', 'yes'])
                else:
                    setattr(self, key, current_type(value))
                
                await update_db_setting(key, str(value))
                logging.info(f"Configuration updated: {key} = {value}")
            except (ValueError, TypeError) as e:
                 logging.error(f"Invalid value type for config key '{key}'. Expected {current_type}. Error: {e}")
        else:
            logging.warning(f"Attempted to update non-existent config key: {key}")

config = Config()
