import logging
from typing import Optional, Tuple
from .base import MediaResult
from .tiktok import TikTokDownloader
from .instagram import InstagramDownloader

logger = logging.getLogger("MediaDownloaderBot.Manager")


class MediaManager:
    """Central manager to detect platform and orchestrate downloads."""

    def __init__(self):
        self.tiktok_downloader = TikTokDownloader()
        self.instagram_downloader = InstagramDownloader()

    def find_supported_url(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Scans text for supported media URLs.
        Returns tuple of (platform, url) if found, else None.
        """
        if not text:
            return None

        # Check TikTok
        tiktok_url = self.tiktok_downloader.extract_url(text)
        if tiktok_url:
            return ("TikTok", tiktok_url)

        # Check Instagram
        ig_url = self.instagram_downloader.extract_url(text)
        if ig_url:
            return ("Instagram", ig_url)

        return None

    async def download_media(self, platform: str, url: str) -> MediaResult:
        """Dispatches download to the appropriate downloader."""
        logger.info("Processing %s URL: %s", platform, url)

        if platform == "TikTok":
            return await self.tiktok_downloader.download(url)
        elif platform == "Instagram":
            return await self.instagram_downloader.download(url)
        else:
            return MediaResult(
                platform=platform,
                original_url=url,
                success=False,
                error_message=f"Unsupported platform: {platform}"
            )
