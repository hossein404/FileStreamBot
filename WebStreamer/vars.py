# WebStreamer/vars.py

import os
import logging
import sys
from os import getenv
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] ==> %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S'
)

class Var(object):
    """A class to hold all environment variables."""
    
    # --- Mandatory Environment Variables Check ---
    mandatory_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'OWNER_ID', 'BIN_CHANNEL']
    missing_vars = [v for v in mandatory_vars if not getenv(v)]
    if missing_vars:
        logging.critical(f"FATAL: Missing mandatory environment variables: {missing_vars}")
        sys.exit(1)

    API_ID = int(getenv('API_ID'))
    API_HASH = str(getenv('API_HASH'))
    BOT_TOKEN = str(getenv('BOT_TOKEN'))
    OWNER_ID = int(getenv('OWNER_ID'))
    BIN_CHANNEL = int(getenv('BIN_CHANNEL'))
    
    # --- Other Configurations ---
    DATABASE_URL = getenv('DATABASE_URL', None) # Not used with SQLite
    PORT = int(getenv('PORT', 8080))
    BIND_ADDRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
    
    ON_HEROKU = 'DYNO' in os.environ
    FQDN = getenv('FQDN')
    if ON_HEROKU and not FQDN:
        APP_NAME = getenv('APP_NAME')
        if not APP_NAME:
            logging.critical("FATAL: APP_NAME env var is required on Heroku.")
            sys.exit(1)
        FQDN = f"{APP_NAME}.herokuapp.com"
    elif not FQDN:
        FQDN = BIND_ADDRESS

    HAS_SSL = getenv('HAS_SSL', 'false').lower() == 'true'
    URL = f"https://{FQDN}/" if HAS_SSL else f"http://{FQDN}:{PORT}/"
    
    DEBUG = getenv('DEBUG', 'false').lower() == 'true'
    RATE_LIMIT = getenv('RATE_LIMIT', 'false').lower() == 'true'
    MAX_REQUESTS = int(getenv('MAX_REQUESTS', '5'))
    TIME_WINDOW = int(getenv('TIME_WINDOW', '60'))
    SLEEP_THRESHOLD = int(getenv('SLEEP_THRESHOLD', '60'))
    WORKERS = int(getenv('WORKERS', '4'))
    PING_INTERVAL = int(getenv('PING_INTERVAL', '1200'))
    USE_SESSION_FILE = getenv('USE_SESSION_FILE', 'false').lower() == 'true'
    
    # ALLOWED_USERS is now deprecated in favor of database-driven user management
    # It can still be used as an initial list of admins if needed, but not for general access
    ALLOWED_USERS = [int(user) for user in getenv('ALLOWED_USERS', '').split(',') if user]
    
    HASH_LENGTH = int(getenv('HASH_LENGTH', '6'))
    ADMIN_USERNAME = getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = getenv('ADMIN_PASSWORD', 'password')
    KEEP_ALIVE = getenv('KEEP_ALIVE', 'false').lower() == 'true'
    MULTI_CLIENT = False
