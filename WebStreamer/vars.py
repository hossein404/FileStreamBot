# WebStreamer/vars.py
import os
import logging
import sys
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# Logging is now handled exclusively in __main__.py to prevent duplicate logs.

class Var(object):
    mandatory_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'OWNER_ID', 'BIN_CHANNEL']
    missing_vars = [v for v in mandatory_vars if not getenv(v)]
    if missing_vars:
        # Use print here because logging might not be configured yet
        print(f"FATAL: Missing mandatory environment variables: {missing_vars}")
        sys.exit(1)

    API_ID = int(getenv('API_ID'))
    API_HASH = str(getenv('API_HASH'))
    BOT_TOKEN = str(getenv('BOT_TOKEN'))
    OWNER_ID = int(getenv('OWNER_ID'))
    BIN_CHANNEL = int(getenv('BIN_CHANNEL'))
    
    PORT = int(getenv('PORT', 8080))
    BIND_ADDRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
    
    ON_HEROKU = 'DYNO' in os.environ
    FQDN = getenv('FQDN')
    if ON_HEROKU and not FQDN:
        APP_NAME = getenv('APP_NAME')
        if not APP_NAME:
            print("FATAL: APP_NAME env var is required on Heroku.")
            sys.exit(1)
        FQDN = f"{APP_NAME}.herokuapp.com"
    elif not FQDN:
        FQDN = BIND_ADDRESS

    HAS_SSL = getenv('HAS_SSL', 'false').lower() == 'true'
    URL = f"https://{FQDN}/" if HAS_SSL else f"http://{FQDN}:{PORT}/"
    
    DEBUG = getenv('DEBUG', 'false').lower() == 'true'
    # These variables were missing in the previous version I provided
    RATE_LIMIT = getenv('RATE_LIMIT', 'false').lower() == 'true'
    MAX_REQUESTS = int(getenv('MAX_REQUESTS', '5'))
    TIME_WINDOW = int(getenv('TIME_WINDOW', '60'))
    
    SLEEP_THRESHOLD = int(getenv('SLEEP_THRESHOLD', '60'))
    WORKERS = int(getenv('WORKERS', '4'))
    PING_INTERVAL = int(getenv('PING_INTERVAL', '1200'))
    USE_SESSION_FILE = getenv('USE_SESSION_FILE', 'false').lower() == 'true'
    
    HASH_LENGTH = int(getenv('HASH_LENGTH', '6'))
    ADMIN_USERNAME = getenv('ADMIN_USERNAME', 'admin')
    
    ADMIN_PASSWORD_HASH = getenv('ADMIN_PASSWORD_HASH')
    if not ADMIN_PASSWORD_HASH:
        print("FATAL: ADMIN_PASSWORD_HASH environment variable is not set!")
        print("Please run 'python3 generate_hash.py' to create a hash and add it to your .env file.")
        sys.exit(1)

    KEEP_ALIVE = getenv('KEEP_ALIVE', 'false').lower() == 'true'
    MULTI_CLIENT = False