import os
import asyncio
import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import TelegramError

from downloader.base import MediaType, MediaResult
from downloader.manager import MediaManager
import config
import tracker

logger = logging.getLogger("MediaDownloaderBot.MediaHandler")
media_manager = MediaManager()


def _format_caption(result: MediaResult) -> str:
    """Formats a clean Telegram caption (max 1024 characters)."""
    caption_parts = []

    if result.title:
        title = result.title.strip()
        if len(title) > 300:
            title = title[:297] + "..."
        caption_parts.append(f"📝 {title}")

    if result.author:
        caption_parts.append(f"👤 Author: {result.author}")

    caption_parts.append(f"🔗 Original Link:\n{result.original_url}")

    full_caption = "\n\n".join(caption_parts)
    if len(full_caption) > 1024:
        full_caption = full_caption[:1020] + "..."
    return full_caption


def _escape_md(text: str) -> str:
    """Escape special Markdown characters in error text to prevent parse failures."""
    for ch in ('_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'):
        text = text.replace(ch, f"\\{ch}")
    return text


async def _delayed_delete(message, delay: int = 5):
    """Deletes a Telegram message after a specified delay."""
    if not message:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except TelegramError:
        pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming user messages for TikTok and Instagram links."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id if update.effective_user else None
    if config.ALLOWED_USERS and user_id not in config.ALLOWED_USERS:
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    text = update.message.text.strip()

    # Handle "clear all" text command
    if text.lower() == "clear all":
        chat_id = update.effective_chat.id
        msg_ids = tracker.get_and_clear_messages(chat_id)
        deleted_count = 0
        for msg_id in msg_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                deleted_count += 1
            except TelegramError:
                pass

        try:
            await update.message.delete()
        except TelegramError:
            pass

        status = await context.bot.send_message(
            chat_id=chat_id,
            text=f"🧹 Cleared {deleted_count} messages from chat history!"
        )
        asyncio.create_task(_delayed_delete(status, 5))
        return

    match = media_manager.find_supported_url(text)
    if not match:
        return

    platform, url = match
    status_msg = await update.message.reply_text(
        f"⚡ Found {platform} link!\n⏳ Fetching media in highest quality..."
    )

    result = None
    try:
        # Download media
        result = await media_manager.download_media(platform, url)

        if not result.success or not result.media_files:
            error_text = result.error_message or "Could not download media from the provided link."
            await status_msg.edit_text(f"❌ Download Failed\n{error_text}")

            # Track for clear_all
            chat_id = update.effective_chat.id
            tracker.add_message(chat_id, update.message.message_id)
            tracker.add_message(chat_id, status_msg.message_id)
            return

        await status_msg.edit_text("⬆️ Uploading to Telegram...")
        caption = _format_caption(result)

        sent_messages = []

        # 1. Single video
        if len(result.media_files) == 1 and result.media_files[0].media_type == MediaType.VIDEO:
            video_file = result.media_files[0]
            if video_file.file_size > config.MAX_FILE_SIZE_BYTES:
                await status_msg.edit_text(
                    f"⚠️ The video size ({video_file.file_size / (1024*1024):.1f} MB) exceeds Telegram bot limit ({config.MAX_FILE_SIZE_MB} MB)."
                )
                chat_id = update.effective_chat.id
                tracker.add_message(chat_id, update.message.message_id)
                tracker.add_message(chat_id, status_msg.message_id)
                return

            with open(video_file.file_path, "rb") as f:
                msg = await update.message.reply_video(
                    video=f,
                    caption=caption,
                    duration=video_file.duration,
                    width=video_file.width,
                    height=video_file.height,
                    supports_streaming=True
                )
                sent_messages.append(msg)

        # 2. Single photo
        elif len(result.media_files) == 1 and result.media_files[0].media_type == MediaType.PHOTO:
            photo_file = result.media_files[0]
            with open(photo_file.file_path, "rb") as f:
                msg = await update.message.reply_photo(
                    photo=f,
                    caption=caption,
                )
                sent_messages.append(msg)

        # 3. Multiple media / Carousels / Slideshows
        else:
            visual_files = [m for m in result.media_files if m.media_type in (MediaType.PHOTO, MediaType.VIDEO)]
            audio_files = [m for m in result.media_files if m.media_type == MediaType.AUDIO]

            # Send visual files in albums (Telegram supports 2-10 items per group)
            chunk_size = 10
            for i in range(0, len(visual_files), chunk_size):
                chunk = visual_files[i:i + chunk_size]

                # Single item chunk (fallback to single photo/video)
                if len(chunk) == 1:
                    item = chunk[0]
                    item_caption = caption if i == 0 else None
                    if item.media_type == MediaType.VIDEO:
                        with open(item.file_path, "rb") as f:
                            msg = await update.message.reply_video(
                                video=f,
                                caption=item_caption,
                                duration=item.duration,
                                width=item.width,
                                height=item.height,
                                supports_streaming=True
                            )
                            sent_messages.append(msg)
                    else:
                        with open(item.file_path, "rb") as f:
                            msg = await update.message.reply_photo(
                                photo=f,
                                caption=item_caption,
                            )
                            sent_messages.append(msg)
                else:
                    # Multi-item chunk (2 to 10 items)
                    media_group = []
                    opened_files = []

                    for idx, item in enumerate(chunk):
                        f = open(item.file_path, "rb")
                        opened_files.append(f)

                        item_caption = caption if (i == 0 and idx == 0) else None

                        if item.media_type == MediaType.VIDEO:
                            media_group.append(InputMediaVideo(
                                media=f,
                                caption=item_caption,
                                supports_streaming=True
                            ))
                        else:
                            media_group.append(InputMediaPhoto(
                                media=f,
                                caption=item_caption,
                            ))

                    try:
                        msgs = await update.message.reply_media_group(media=media_group)
                        sent_messages.extend(msgs)
                    finally:
                        for f in opened_files:
                            f.close()

                # Short delay between consecutive album sends to avoid flood limits
                if i + chunk_size < len(visual_files):
                    await asyncio.sleep(0.5)

            # Send soundtrack if available (e.g. TikTok background music)
            for audio_item in audio_files:
                with open(audio_item.file_path, "rb") as f:
                    msg = await update.message.reply_audio(
                        audio=f,
                        title=f"{result.author or 'TikTok'} - Soundtrack",
                        caption="🎵 Background Music Track"
                    )
                    sent_messages.append(msg)

        # Clean up status message immediately after success
        try:
            await status_msg.delete()
        except TelegramError:
            pass

        # Track messages for clear_all
        chat_id = update.effective_chat.id
        for msg in sent_messages:
            tracker.add_message(chat_id, msg.message_id)

        # Auto-delete the user's original link message after 5s
        asyncio.create_task(_delayed_delete(update.message, 5))

    except Exception as e:
        logger.exception("Error processing link %s: %s", url, e)
        try:
            await status_msg.edit_text(f"❌ Error processing link: {str(e)[:150]}")
            chat_id = update.effective_chat.id
            tracker.add_message(chat_id, update.message.message_id)
            tracker.add_message(chat_id, status_msg.message_id)
        except TelegramError:
            pass
    finally:
        if result:
            result.cleanup()


def register_media_handlers(app):
    """Registers media message handlers."""
    app.add_handler(
        MessageHandler(
            filters.TEXT & (~filters.COMMAND),
            handle_message
        )
    )
