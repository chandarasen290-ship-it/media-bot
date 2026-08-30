import json
import os
import logging
from threading import Lock
from pathlib import Path

logger = logging.getLogger("MediaDownloaderBot.Tracker")

# Use absolute path relative to project root so it works regardless of cwd
HISTORY_FILE = str(Path(__file__).parent / "chat_history.json")
_lock = Lock()


def load_history():
    """Load message history from disk."""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Error loading history: %s", e)
        return {}


def save_history(history):
    """Persist message history to disk."""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except IOError as e:
        logger.error("Error saving history: %s", e)


def add_message(chat_id, message_id):
    """Track a message ID for later deletion."""
    with _lock:
        chat_id_str = str(chat_id)
        history = load_history()
        if chat_id_str not in history:
            history[chat_id_str] = []
        if message_id not in history[chat_id_str]:
            history[chat_id_str].append(message_id)
        save_history(history)


def get_and_clear_messages(chat_id):
    """Retrieve all tracked message IDs for a chat and clear the history."""
    with _lock:
        chat_id_str = str(chat_id)
        history = load_history()
        messages = history.get(chat_id_str, [])
        if chat_id_str in history:
            history[chat_id_str] = []
            save_history(history)
        return messages
