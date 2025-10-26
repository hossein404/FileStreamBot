import os
import sys
from os import getenv
from dotenv import load_dotenv

load_dotenv()

class Var(object):
    # الزامی‌ها را از .env بخوان و اگر نبودند، متوقف شو
    mandatory_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'OWNER_ID', 'BIN_CHANNEL']
    missing_vars = [v for v in mandatory_vars if not getenv(v)]
    if missing_vars:
        print(f"FATAL: Missing mandatory environment variables: {missing_vars}")
        sys.exit(1)

    # کلیدها/شناسه‌ها
    API_ID = int(getenv('API_ID'))
    API_HASH = str(getenv('API_HASH'))
    BOT_TOKEN = str(getenv('BOT_TOKEN'))
    OWNER_ID = int(getenv('OWNER_ID'))
    BIN_CHANNEL = int(getenv('BIN_CHANNEL'))

    # وب‌سرور: پورت داخلی و پورت عمومی (برای ساخت لینک)
    PORT = int(getenv('PORT', 8080))                           # پورت bind داخلی (مثلاً 800)
    PUBLIC_PORT = int(getenv('PUBLIC_PORT', PORT))             # پورت لینک عمومی (مثلاً 80/443)
    BIND_ADDRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))

    # دامنه / FQDN
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

    # SSL
    HAS_SSL = getenv('HAS_SSL', 'false').lower() == 'true'

    # ساخت URL عمومی: اگر روی 80/443 هست، پورت را ننویس
    if HAS_SSL:
        URL = f"https://{FQDN}/" if PUBLIC_PORT in (443, 0) else f"https://{FQDN}:{PUBLIC_PORT}/"
    else:
        URL = f"http://{FQDN}/"  if PUBLIC_PORT in (80, 0)  else f"http://{FQDN}:{PUBLIC_PORT}/"

    # سایر تنظیمات
    DEBUG = getenv('DEBUG', 'false').lower() == 'true'
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
