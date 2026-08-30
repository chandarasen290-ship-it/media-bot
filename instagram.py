import os
import re
import uuid
import logging
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
import yt_dlp
import instaloader

from .base import MediaResult, MediaFile, MediaType
import config

logger = logging.getLogger("MediaDownloaderBot.Instagram")

# Regex for posts/reels/tv/share — captures shortcode in group(2)
INSTAGRAM_POST_REGEX = re.compile(
    r"(https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:reel|reels|p|tv|share)/([a-zA-Z0-9_\-\.]+)/?(?:\?[^\s]*)?)",
    re.IGNORECASE
)

# Regex for stories — captures username in group(2) and optional story_id in group(3)
INSTAGRAM_STORY_REGEX = re.compile(
    r"(https?://(?:www\.)?(?:instagram\.com|instagr\.am)/stories/([a-zA-Z0-9_\-\.]+)(?:/([0-9]+))?/?(?:\?[^\s]*)?)",
    re.IGNORECASE
)

# Combined regex for URL detection (matches any Instagram URL)
INSTAGRAM_REGEX = re.compile(
    r"(https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:reel|reels|p|tv|stories|share)/[a-zA-Z0-9_\-\.]+(?:/[a-zA-Z0-9_\-\.]*)?/?(?:\?[^\s]*)?)",
    re.IGNORECASE
)


def _get_instaloader():
    """Create a fresh Instaloader instance to avoid stale session issues."""
    return instaloader.Instaloader(
        quiet=True,
        download_video_thumbnails=False,
        save_metadata=False
    )


class InstagramDownloader:
    """Downloader specialized for high-speed and maximum quality Instagram media."""

    @staticmethod
    def is_instagram_url(url: str) -> bool:
        return bool(INSTAGRAM_REGEX.search(url))

    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        match = INSTAGRAM_REGEX.search(text)
        return match.group(0) if match else None

    def _is_story_url(self, url: str) -> bool:
        return bool(INSTAGRAM_STORY_REGEX.search(url))

    async def download(self, url: str) -> MediaResult:
        """Downloads Instagram media asynchronously."""
        session_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config.TEMP_DIR, f"ig_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)

        result = MediaResult(platform="Instagram", original_url=url, temp_dir=temp_dir)

        # Route: Story URLs need special handling
        if self._is_story_url(url):
            return await self._handle_story(url, temp_dir, result)

        # Route: Posts / Reels / TV
        return await self._handle_post(url, temp_dir, result)

    async def _handle_post(self, url: str, temp_dir: str, result: MediaResult) -> MediaResult:
        """Handle Instagram posts, reels, TV."""
        # 1. Try yt-dlp first
        try:
            yt_result = await asyncio.to_thread(self._download_ytdlp, url, temp_dir, result)
            if yt_result.success and yt_result.media_files:
                return yt_result
        except Exception as e:
            logger.warning("yt-dlp extraction failed for %s: %s", url, e)

        # 2. Fallback to Instaloader for public posts
        match = INSTAGRAM_POST_REGEX.search(url)
        if match:
            shortcode = match.group(2)
            if shortcode:
                logger.info("yt-dlp blocked. Falling back to Instaloader for shortcode: %s", shortcode)
                try:
                    result.media_files.clear()
                    result.success = True
                    result.error_message = None
                    il_result = await self._download_instaloader_post(shortcode, temp_dir, result)
                    if il_result and il_result.media_files:
                        return il_result
                except Exception as e:
                    logger.error("Instaloader fallback failed: %s", e)

        # Both failed
        result.success = False
        result.error_message = (
            "Instagram has blocked access to this post (it may be private, or rate-limited).\n"
            "To fix this, please supply a cookies.txt file to the bot."
        )
        return result

    async def _handle_story(self, url: str, temp_dir: str, result: MediaResult) -> MediaResult:
        """Handle Instagram story URLs."""
        match = INSTAGRAM_STORY_REGEX.search(url)
        if not match:
            result.success = False
            result.error_message = "Invalid Instagram story URL."
            return result

        username = match.group(2)
        story_id = match.group(3)  # may be None if URL is just /stories/username/

        # 1. Try yt-dlp first (works if cookies are available)
        try:
            yt_result = await asyncio.to_thread(self._download_ytdlp, url, temp_dir, result)
            if yt_result.success and yt_result.media_files:
                return yt_result
        except Exception as e:
            logger.warning("yt-dlp story extraction failed for %s: %s", url, e)

        # 2. Fallback to Instaloader for stories
        logger.info("Falling back to Instaloader for story by @%s (id: %s)", username, story_id or "all")
        try:
            result.media_files.clear()
            result.success = True
            result.error_message = None
            il_result = await self._download_instaloader_story(username, story_id, temp_dir, result)
            if il_result and il_result.media_files:
                return il_result
        except Exception as e:
            logger.error("Instaloader story fallback failed: %s", e)

        # Both failed
        result.success = False
        result.error_message = (
            f"Could not download Instagram story from @{username}.\n"
            "Stories require login. Please supply a cookies.txt file to the bot."
        )
        return result

    def _download_ytdlp(self, url: str, temp_dir: str, result: MediaResult) -> MediaResult:
        out_template = os.path.join(temp_dir, "%(autonumber)02d_%(id)s.%(ext)s")

        ydl_opts = {
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
            "max_filesize": config.MAX_FILE_SIZE_BYTES,
            "concurrent_fragment_downloads": 16,
            "buffersize": 1048576,
            "http_chunk_size": 10485760,
            "retries": 3,
            "socket_timeout": 15,
            "nocheckcertificate": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            },
        }

        if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
            ydl_opts["cookiefile"] = config.COOKIES_FILE
            logger.info("Using cookies file for Instagram: %s", config.COOKIES_FILE)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                result.success = False
                result.error_message = "No media found in the Instagram URL."
                return result

            result.title = info.get("title", "") or info.get("description", "")
            result.author = info.get("uploader", "") or info.get("channel", "")
            result.caption = result.title or "Instagram Media"

            if result.title and len(result.title) > 300:
                result.title = result.title[:297] + "..."

            downloaded_files = sorted([
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f))
            ])

            for file_path in downloaded_files:
                ext = Path(file_path).suffix.lower()
                if ext in [".mp4", ".mkv", ".webm", ".mov"]:
                    result.media_files.append(
                        MediaFile(
                            file_path=file_path,
                            media_type=MediaType.VIDEO,
                            duration=info.get("duration"),
                            width=info.get("width"),
                            height=info.get("height"),
                        )
                    )
                elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    result.media_files.append(
                        MediaFile(file_path=file_path, media_type=MediaType.PHOTO)
                    )

            if not result.media_files:
                result.success = False
                result.error_message = "Could not extract media files."

        return result

    async def _download_instaloader_post(self, shortcode: str, temp_dir: str, result: MediaResult) -> Optional[MediaResult]:
        """Fallback to Instaloader to extract direct video/photo URLs for public posts."""
        L = _get_instaloader()
        try:
            post = await asyncio.to_thread(instaloader.Post.from_shortcode, L.context, shortcode)
        except Exception as e:
            raise Exception(f"Instaloader could not fetch post {shortcode}: {e}")

        result.author = post.owner_username

        post_caption = post.caption or "Instagram Post"
        if len(post_caption) > 300:
            post_caption = post_caption[:297] + "..."
        result.caption = post_caption
        result.title = post_caption

        urls_to_download = []

        if post.typename == "GraphVideo":
            urls_to_download.append((post.video_url, MediaType.VIDEO))
        elif post.typename == "GraphImage":
            urls_to_download.append((post.url, MediaType.PHOTO))
        elif post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    urls_to_download.append((node.video_url, MediaType.VIDEO))
                else:
                    urls_to_download.append((node.display_url, MediaType.PHOTO))

        if not urls_to_download:
            return None

        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, (media_url, m_type) in enumerate(urls_to_download):
                ext = ".mp4" if m_type == MediaType.VIDEO else ".jpg"
                file_path = os.path.join(temp_dir, f"media_{idx:02d}{ext}")

                try:
                    async with session.get(media_url) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(file_path, "wb") as f:
                                async for chunk in resp.content.iter_chunked(1024 * 1024):
                                    await f.write(chunk)
                            result.media_files.append(MediaFile(file_path=file_path, media_type=m_type))
                except Exception as e:
                    logger.warning("Failed to download media item %d: %s", idx, e)

        if not result.media_files:
            return None

        return result

    async def _download_instaloader_story(self, username: str, story_id: Optional[str], temp_dir: str, result: MediaResult) -> Optional[MediaResult]:
        """Download Instagram stories using Instaloader.
        
        Stories require authentication. Instaloader can use a saved session
        from a previous `instaloader --login` command, or we try anonymously.
        """
        L = _get_instaloader()

        # Try to load a saved session if available
        session_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ig_session")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    ig_user = f.read().strip()
                if ig_user:
                    L.load_session_from_file(ig_user)
                    logger.info("Loaded Instaloader session for user: %s", ig_user)
            except Exception as e:
                logger.warning("Failed to load Instaloader session: %s", e)

        try:
            # Get the profile
            profile = await asyncio.to_thread(instaloader.Profile.from_username, L.context, username)
        except Exception as e:
            raise Exception(f"Could not find Instagram profile @{username}: {e}")

        result.author = username
        result.title = f"Story by @{username}"
        result.caption = result.title

        urls_to_download = []

        try:
            # Get stories for this user
            stories = await asyncio.to_thread(lambda: list(L.get_stories(userids=[profile.userid])))

            if not stories:
                raise Exception(f"No active stories found for @{username}")

            for story in stories:
                for item in story.get_items():
                    # If a specific story_id was requested, only download that one
                    if story_id and str(item.mediaid) != story_id:
                        continue

                    if item.is_video:
                        urls_to_download.append((item.video_url, MediaType.VIDEO))
                    else:
                        urls_to_download.append((item.url, MediaType.PHOTO))

                    # If specific story_id was found, stop searching
                    if story_id and str(item.mediaid) == story_id:
                        break

        except instaloader.exceptions.LoginRequiredException:
            raise Exception(
                "Instagram requires login to view stories. "
                "Please run 'instaloader --login YOUR_USERNAME' on the server to save a session, "
                "then create a file called 'ig_session' containing your username."
            )

        if not urls_to_download:
            if story_id:
                raise Exception(f"Story {story_id} not found or has expired for @{username}")
            else:
                raise Exception(f"No active stories found for @{username}")

        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, (media_url, m_type) in enumerate(urls_to_download):
                ext = ".mp4" if m_type == MediaType.VIDEO else ".jpg"
                file_path = os.path.join(temp_dir, f"story_{idx:02d}{ext}")

                try:
                    async with session.get(media_url) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(file_path, "wb") as f:
                                async for chunk in resp.content.iter_chunked(1024 * 1024):
                                    await f.write(chunk)
                            result.media_files.append(MediaFile(file_path=file_path, media_type=m_type))
                except Exception as e:
                    logger.warning("Failed to download story item %d: %s", idx, e)

        if not result.media_files:
            return None

        return result
