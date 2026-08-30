import sys
import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram.ext import ApplicationBuilder

import config
from handlers import register_command_handlers, register_media_handlers

logger = logging.getLogger("MediaDownloaderBot.Main")

# --- Dummy Web Server for Cloud Hosting (Render) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
# ---------------------------------------------------

def main():
    import os
    keep_alive()
    """Starts the Telegram bot with optimized network and concurrency configuration."""
    if not config.BOT_TOKEN:
        print("\n" + "=" * 60)
        print("❌ ERROR: BOT_TOKEN is not set!")
        print("Please create a .env file with your Telegram Bot Token:")
        print("BOT_TOKEN=your_token_from_botfather")
        print("=" * 60 + "\n")
        sys.exit(1)

    print("🤖 Starting High-Speed Telegram Media Downloader Bot...")
    print(f"📁 Temp directory: {config.TEMP_DIR}")
    print(f"🍪 Cookies file: {config.COOKIES_FILE if config.COOKIES_FILE else 'None'}")
    if config.ALLOWED_USERS:
        print(f"🔒 Allowed users: {len(config.ALLOWED_USERS)} user(s)")
    else:
        print("🌍 Access mode: Public (Anyone can use the bot)")

    # Build Telegram Bot application with optimized connection pooling & timeouts for HD media
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .concurrent_updates(True)
        .connection_pool_size(32)
        .get_updates_connection_pool_size(8)
        .read_timeout(120)
        .write_timeout(180)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Register handlers
    register_command_handlers(app)
    register_media_handlers(app)

    print("✅ Bot is online with MAX speed & HD quality! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
