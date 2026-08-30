import os
import asyncio
import logging
import shutil
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.error import TelegramError

import config
import tracker

logger = logging.getLogger("MediaDownloaderBot.Commands")


async def _delayed_delete(message, delay: int = 5):
    """Deletes a Telegram message after a specified delay."""
    if not message:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except TelegramError:
        pass


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command."""
    user_name = update.effective_user.first_name if update.effective_user else "there"
    welcome_text = (
        f"👋 **Hello {user_name}!**\n\n"
        f"I am your **TikTok & Instagram Downloader Bot** 📥\n\n"
        f"Just send or forward me any link from:\n"
        f"• 🎵 **TikTok**: Videos (no watermark), Photo slideshows, and Stories\n"
        f"• 📸 **Instagram**: Reels, Posts (Photos/Videos/Carousels), and Stories\n\n"
        f"✨ *No complex commands needed — simply paste your link and I will auto-download it!*\n\n"
        f"🧹 Type **clear all** to delete all bot messages from chat."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /help command."""
    help_text = (
        "📖 **How to use this bot:**\n\n"
        "1. **TikTok**:\n"
        "   • Copy link to any video, photo post, or story.\n"
        "   • Supported: `vt.tiktok.com/...`, `tiktok.com/@user/video/...`, `tiktok.com/@user/photo/...`\n\n"
        "2. **Instagram**:\n"
        "   • Copy link to any Reel, Post, or Story.\n"
        "   • Supported: `instagram.com/reel/...`, `instagram.com/p/...`, `instagram.com/stories/...`\n\n"
        "3. **Features**:\n"
        "   • 🎥 Watermark-free video downloads\n"
        "   • 🖼️ Multi-photo carousels delivered as Telegram albums\n"
        "   • 🎵 Background audio track extraction for photo slideshows\n"
        "   • 🍪 Cookie support for private posts & stories (see /cookies)\n\n"
        "4. **Chat cleanup**:\n"
        "   • Type **clear all** to delete all bot messages from chat\n"
        "   • Use /clear\\_all command for the same effect\n\n"
        "💬 Send me a link now to test it!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /cookies command with setup instructions."""
    cookies_exist = config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE)
    status_icon = "✅ Loaded" if cookies_exist else "⚠️ Not configured"

    cookie_text = (
        f"🍪 **Cookies Status**: {status_icon}\n\n"
        "**Why use cookies?**\n"
        "Instagram and TikTok restrict access to Stories or content from private accounts you follow.\n\n"
        "**How to configure cookies (for bot admin):**\n"
        "1. Install a browser extension like *'Get cookies.txt LOCALLY'* (Chrome/Firefox).\n"
        "2. Log in to Instagram or TikTok in your browser.\n"
        "3. Export the cookies in Netscape format as `cookies.txt`.\n"
        "4. Place `cookies.txt` in the bot's root directory."
    )
    await update.message.reply_text(cookie_text, parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /status command."""
    cookies_exist = config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE)
    msg = (
        "⚙️ **Bot Status**:\n"
        f"• Status: 🟢 Online\n"
        f"• Max File Size: {config.MAX_FILE_SIZE_MB} MB\n"
        f"• Cookies: {'✅ Configured' if cookies_exist else '❌ None'}\n"
        f"• Access: {'🔒 Whitelisted' if config.ALLOWED_USERS else '🌍 Public'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def clear_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /clear_all command to wipe downloaded files from disk and clean chat history."""
    user_id = update.effective_user.id if update.effective_user else None
    if config.ALLOWED_USERS and user_id not in config.ALLOWED_USERS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    status_msg = await update.message.reply_text("🧹 Clearing all cached downloads and chat history...")

    # 1. Clear chat messages
    chat_id = update.effective_chat.id
    msg_ids = tracker.get_and_clear_messages(chat_id)
    chat_deleted = 0
    for msg_id in msg_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            chat_deleted += 1
        except TelegramError:
            pass

    # Delete the /clear_all command message itself
    try:
        await update.message.delete()
    except TelegramError:
        pass

    # 2. Clear temp dir
    disk_deleted = 0
    try:
        temp_dir = config.TEMP_DIR
        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    disk_deleted += 1
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Error clearing temp dir: %s", e)

    await status_msg.edit_text(
        f"✅ **Storage & Chat Cleared!**\nDeleted {chat_deleted} chat messages and {disk_deleted} disk items.",
        parse_mode="Markdown"
    )

    # Auto delete the status message after 5 seconds to keep chat clean
    asyncio.create_task(_delayed_delete(status_msg, 5))


def register_command_handlers(app):
    """Registers all bot command handlers."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cookies", cookies_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear_all", clear_all_command))
