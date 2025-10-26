<div align="center">

#  Telegram File Stream Bot 🚀

<p>
  A powerful and efficient Telegram bot that generates direct, streamable links for your Telegram files, now with a persistent, secure admin panel powered by Redis.
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/Framework-Pyrogram%20%7C%20AIOHTTP-orange?style=for-the-badge" alt="Framework">
  <img src="https://img.shields.io/github/stars/iamast3r/TG-File2Link?style=for-the-badge&logo=github&label=Stars" alt="GitHub Stars">
  <img src="https://img.shields.io/github/forks/iamast3r/TG-File2Link?style=for-the-badge&logo=github&label=Forks" alt="GitHub Forks">
</p>

[🇮🇷 **Read in Persian / خواندن به زبان فارسی**](./READMEfa.md)

</div>

---

## ✨ Features

-   **Instant Link Generation**: Get a direct download/stream link for any file you forward to the bot.
-   **Large File Support**: No file size limitations (subject to Telegram's limits).
-   **High-Speed Streaming**: Links are generated on the fly without downloading files to your server first.
-   **Secure & Persistent Web Admin Panel**: Manage users and view statistics through a simple and secure web interface with password hashing, CSRF protection, and persistent sessions via Redis.
-   **Secure**: Restrict access to authorized users and specific channels.
-   **Easy to Deploy**: Get your bot up and running with just a few simple commands.

## 🔧 Installation & Deployment

Follow these steps to deploy the bot:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hossein404/FileStreamBot.git
    cd FileStreamBot
    ```

2.  **Install Prerequisites (Redis):**
    This project requires Redis for persistent admin sessions. Install it on your server.
    ```bash
    # For Debian/Ubuntu
    sudo apt update
    sudo apt install redis-server -y
    sudo systemctl enable redis-server.service
    ```

3.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv ./venv
    source ./venv/bin/activate
    ```
    *(On Windows, use `.\venv\Scripts\activate`)*

4.  **Install the required dependencies:**
    ```bash
    pip3 install -r requirements.txt
    ```

5.  **Configure environment variables:**
    Create a `.env` file by copying the structure below and fill in your details.

    ```ini
    # Get this from my.telegram.org
    API_ID=
    API_HASH=

    # Get this from @BotFather
    BOT_TOKEN=

    # This is a channel ID for storing files. The bot must be an admin in this channel.
    # It can be a public or private channel. For private channels, use its negative ID (e.g., -100123456789).
    BIN_CHANNEL=

    # Your Telegram user ID. The bot will recognize you as the owner.
    OWNER_ID=

    # The port on which the web server will listen. Default is 8080.
    PORT=

    # Your server's public IP address or a Fully Qualified Domain Name (FQDN).
    FQDN=

    # Set to "true" if you are using SSL/TLS (HTTPS), otherwise "false".
    HAS_SSL=

    # Set to "true" to save pyrogram session files.
    USE_SESSION_FILE=

    # Credentials for the web admin panel.
    ADMIN_USERNAME=
    ADMIN_PASSWORD_HASH= # Generate this in the next step

    # Redis URL for persistent admin sessions
    REDIS_URL=redis://localhost:6379/0
    ```

6.  **Set Admin Password (Securely):**
    Run the included script to generate a secure hash for your desired password.
    ```bash
    python3 generate_hash.py
    ```
    Enter your password when prompted. The script will output a hashed string. Copy this entire string and paste it as the value for `ADMIN_PASSWORD_HASH` in your `.env` file.

7.  **Run the bot:**
    ```bash
    python3 -m WebStreamer
    ```

Your bot is now live and ready to serve!

## 🌐 Web Panel Usage

-   **Access**: You can access the admin panel by navigating to `http://<Your_FQDN>:<PORT>/admin/login` in your web browser.
-   **Login**: Use the `ADMIN_USERNAME` and the password you set in **Step 6** to log in. Your session will now persist even if the bot restarts.
-   **Features**: From the dashboard, you can view bot statistics, manage users (add/remove), and perform other administrative tasks.

## ❤️ Support & Donations

If you find this project helpful and would like to support its development, you can make a donation to the following addresses:

-   **USDT (TRC20):** `TXH1JjrEQZrmQ58FRLkDBHLKZTCZryANrx`
-   **USDT (BEP20):** `0x8aea034cc9ec1e72b79e429716e76aaaef8100b1`
-   **LTC:** `LS1ZiaZEmj3fUxHM99z4mR3qVw4tpzFG3Q`

Your support is greatly appreciated!

## 🤝 Contributing

Contributions are welcome! If you have suggestions or want to improve the code, feel free to open an [issue](https://github.com/iamast3r/TG-File2Link/issues) or submit a [pull request](https://github.com/iamast3r/TG-File2Link/pulls).

## 📝 License

This project is licensed under the [GNU AGPLv3 License](LICENSE).

## 🌟 Credits

This project is a forked and improved version of [TG-FileStreamBot](https://github.com/EverythingSuckz/TG-FileStreamBot).

---
<div align="center">
  <p>Made with ❤️ and Python</p>
</div>
