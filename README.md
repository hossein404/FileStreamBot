<div align="center">

#  TG-File2Link Streamer 🚀

<p>
  A powerful and efficient Telegram bot that generates direct, streamable links for your Telegram files.
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
-   **Secure Web Admin Panel**: Manage users and view statistics through a simple and secure web interface with password hashing and CSRF protection.
-   **Secure**: Restrict access to authorized users and specific channels.
-   **Easy to Deploy**: Get your bot up and running with just a few simple commands.

## 🔧 Installation & Deployment

Follow these steps to deploy the bot:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/iamast3r/TG-File2Link.git
    cd TG-File2Link
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv ./venv
    source ./venv/bin/activate
    ```
    *(On Windows, use `.\venv\Scripts\activate`)*

3.  **Install the required dependencies:**
    ```bash
    pip3 install -r requirements.txt
    ```

4.  **Configure environment variables:**
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
    # If you are on Heroku, this will be automatically detected.
    FQDN=

    # Set to "true" if you are using SSL/TLS (HTTPS), otherwise "false".
    HAS_SSL=

    # Set to "true" to save pyrogram session files, useful for preventing re-logins on restarts.
    # Default is "false" (in-memory session).
    USE_SESSION_FILE=

    # Credentials for the web admin panel.
    ADMIN_USERNAME=

    # HASHED password for the admin panel.
    # See the "Set Admin Password" step below to generate this hash.
    ADMIN_PASSWORD_HASH=
    ```

5.  **Set Admin Password (Securely):**
    Run the included script to generate a secure hash for your desired password.

    ```bash
    python3 generate_hash.py
    ```
    Enter your password when prompted. The script will output a hashed string. Copy this entire string and paste it as the value for `ADMIN_PASSWORD_HASH` in your `.env` file.

6.  **Run the bot:**
    ```bash
    python3 -m WebStreamer
    ```

Your bot is now live and ready to serve!

## 🤖 How to Use

1.  **Start the bot**: Open a chat with your bot and send the `/start` command.
2.  **Forward a file**: Forward any file from any chat or channel to the bot.
3.  **Get the link**: The bot will instantly reply with a direct streamable link.

> **Note:** The bot must be an admin in the source channel if it's a private channel to access the files.

## 🌐 Web Panel Usage

-   **Access**: You can access the admin panel by navigating to `http://<Your_FQDN>:<PORT>/admin/login` in your web browser.
-   **Login**: Use the `ADMIN_USERNAME` and the password you set in **Step 5** to log in.
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
