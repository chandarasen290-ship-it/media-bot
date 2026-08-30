import os
import shutil
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("MediaDownloaderBot.Base")


class MediaType(Enum):
    VIDEO = "video"
    PHOTO = "photo"
    ALBUM = "album"       # Multiple photos/videos combined
    AUDIO = "audio"


@dataclass
class MediaFile:
    file_path: str
    media_type: MediaType
    file_size: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    thumb_path: Optional[str] = None

    def __post_init__(self):
        if not self.file_size and os.path.exists(self.file_path):
            self.file_size = os.path.getsize(self.file_path)


@dataclass
class MediaResult:
    platform: str                    # "TikTok" or "Instagram"
    title: str = ""
    caption: str = ""
    author: str = ""
    original_url: str = ""
    media_files: List[MediaFile] = field(default_factory=list)
    temp_dir: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

    def cleanup(self):
        """Removes temporary files and directory after sending to Telegram."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.debug("Cleaned up temp directory: %s", self.temp_dir)
            except Exception as e:
                logger.warning("Error cleaning up temp directory %s: %s", self.temp_dir, e)
