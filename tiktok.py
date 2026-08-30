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

from .base import MediaResult, MediaFile, MediaType
import config

logger = logging.getLogger("MediaDownloaderBot.TikTok")

TIKTOK_REGEX = re.compile(
    r"(https?://(?:(?:www|m|vt|vm|t)\.)?tiktok\.com/(?:t/[a-zA-Z0-9_-]+|@[^/]+/(?:video|photo|story)/[0-9]+|[^/\s?#]+))",
    re.IGNORECASE
)

CHUNK_SIZE = 1024 * 1024


class TikTokDownloader:
    """Downloader specialized for maximum speed and highest quality TikTok media."""

    @staticmethod
    def is_tiktok_url(url: str) -> bool:
        return bool(TIKTOK_REGEX.search(url))

    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        match = TIKTOK_REGEX.search(text)
        return match.group(0) if match else None

    async def download(self, url: str) -> MediaResult:
        """Attempts download via TikWM API (HD stream) first, with fast yt-dlp fallback."""
        session_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config.TEMP_DIR, f"tiktok_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)

        result = MediaResult(platform="TikTok", original_url=url, temp_dir=temp_dir)

        # 1. Try TikWM API first for ultra-fast HD watermark-free video & slideshows
        try:
            tikwm_res = await self._download_tikwm(url, temp_dir, result)
            if tikwm_res and tikwm_res.media_files:
                return tikwm_res
        except Exception as e:
            logger.warning("TikWM extraction failed for %s: %s. Falling back to yt-dlp.", url, e)

        # 2. Fallback to yt-dlp
        try:
            ytdlp_res = await asyncio.to_thread(self._download_ytdlp, url, temp_dir, result)
            if ytdlp_res and ytdlp_res.media_files:
                return ytdlp_res
        except Exception as e:
            logger.error("yt-dlp extraction failed for %s: %s", url, e)

        # 3. Ultimate fallback: ssstik.io
        try:
            logger.info("Falling back to SSSTIK.io for %s", url)
            ssstik_res = await self._download_ssstik(url, temp_dir, result)
            if ssstik_res and ssstik_res.media_files:
                return ssstik_res
        except Exception as e:
            logger.error("SSSTIK extraction failed for %s: %s", url, e)

        result.success = False
        result.error_message = "Failed to download TikTok media. The post may be private or deleted."
        return result

    async def _download_tikwm(self, url: str, temp_dir: str, result: MediaResult) -> Optional[MediaResult]:
        api_endpoint = "https://www.tikwm.com/api/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        timeout = aiohttp.ClientTimeout(total=45, connect=10)

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(api_endpoint, data={"url": url, "hd": "1"}) as response:
                if response.status != 200:
                    return None
                data = await response.json()

        if not data or data.get("code") != 0 or "data" not in data:
            return None

        info = data["data"]
        result.title = info.get("title", "")
        result.author = info.get("author", {}).get("nickname") or info.get("author", {}).get("unique_id", "")
        result.caption = result.title or "TikTok Media"

        # Case 1: Image slideshow / photo post
        if "images" in info and isinstance(info["images"], list) and len(info["images"]) > 0:
            logger.info("Detected TikTok photo slideshow (%d HD images)", len(info["images"]))
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                for idx, img_url in enumerate(info["images"]):
                    img_path = os.path.join(temp_dir, f"slide_{idx + 1:02d}.jpg")
                    try:
                        async with session.get(img_url) as img_resp:
                            if img_resp.status == 200:
                                async with aiofiles.open(img_path, "wb") as f:
                                    async for chunk in img_resp.content.iter_chunked(CHUNK_SIZE):
                                        await f.write(chunk)
                                result.media_files.append(
                                    MediaFile(file_path=img_path, media_type=MediaType.PHOTO)
                                )
                    except Exception as e:
                        logger.warning("Failed to download slide %d: %s", idx + 1, e)

            # Background music track
            music_url = info.get("music")
            if music_url:
                music_path = os.path.join(temp_dir, "music.mp3")
                try:
                    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                        async with session.get(music_url) as m_resp:
                            if m_resp.status == 200:
                                async with aiofiles.open(music_path, "wb") as f:
                                    async for chunk in m_resp.content.iter_chunked(CHUNK_SIZE):
                                        await f.write(chunk)
                                result.media_files.append(
                                    MediaFile(file_path=music_path, media_type=MediaType.AUDIO)
                                )
                except Exception as e:
                    logger.warning("Failed to download music track: %s", e)
            return result

        # Case 2: Watermark-free Video (Prioritize Highest HD Quality)
        video_url = info.get("hdplay") or info.get("play") or info.get("wmplay")
        if video_url:
            if not video_url.startswith("http"):
                video_url = f"https://www.tikwm.com{video_url}"
            video_path = os.path.join(temp_dir, "video.mp4")

            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(video_url) as v_resp:
                    if v_resp.status == 200:
                        async with aiofiles.open(video_path, "wb") as f:
                            async for chunk in v_resp.content.iter_chunked(CHUNK_SIZE):
                                await f.write(chunk)

                        duration = info.get("duration")
                        width = info.get("hd_width") or info.get("width")
                        height = info.get("hd_height") or info.get("height")

                        result.media_files.append(
                            MediaFile(
                                file_path=video_path,
                                media_type=MediaType.VIDEO,
                                duration=duration,
                                width=width,
                                height=height
                            )
                        )
                        return result
        return None

    def _download_ytdlp(self, url: str, temp_dir: str, result: MediaResult) -> MediaResult:
        out_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
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
        }

        if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
            ydl_opts["cookiefile"] = config.COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return result

            result.title = info.get("title", "")
            result.author = info.get("uploader", "")
            result.caption = result.title or "TikTok Video"

            downloaded_files = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f))
            ]

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

        return result

    async def _download_ssstik(self, url: str, temp_dir: str, result: MediaResult) -> Optional[MediaResult]:
        """Fallback to ssstik.io API when TikTok blocks data center IPs."""
        api_url = "https://ssstik.io/abc?url=dl"
        data = {"id": url, "locale": "en", "tt": "Q2g2elE4"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://ssstik.io",
            "Referer": "https://ssstik.io/en"
        }
        
        timeout = aiohttp.ClientTimeout(total=45, connect=10)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(api_url, data=data) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

        import re
        
        # Check for images first
        image_links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*download[^>]*>', html)
        if image_links:
            logger.info("SSSTIK fallback detected %d images", len(image_links))
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                for idx, img_url in enumerate(image_links):
                    # ssstik puts an audio file as the last link sometimes, we only want jpg/webp/png
                    if "api16-normal" in img_url and "play" in img_url:
                        continue
                    
                    ext = ".jpg"
                    if ".mp3" in img_url or "play" in img_url:
                        ext = ".mp3"
                        
                    file_path = os.path.join(temp_dir, f"media_{idx:02d}{ext}")
                    try:
                        async with session.get(img_url) as img_resp:
                            if img_resp.status == 200:
                                async with aiofiles.open(file_path, "wb") as f:
                                    async for chunk in img_resp.content.iter_chunked(CHUNK_SIZE):
                                        await f.write(chunk)
                                
                                m_type = MediaType.AUDIO if ext == ".mp3" else MediaType.PHOTO
                                result.media_files.append(MediaFile(file_path=file_path, media_type=m_type))
                    except Exception as e:
                        logger.warning("SSSTIK failed to download item %d: %s", idx, e)
                        
            if result.media_files:
                result.title = "TikTok Post"
                result.author = "TikTok"
                result.caption = "Downloaded via Fallback"
                return result
                
        # Check for video
        video_match = re.search(r'href="([^"]+)"[^>]*>Without watermark', html)
        if video_match:
            video_url = video_match.group(1)
            logger.info("SSSTIK fallback detected video")
            video_path = os.path.join(temp_dir, "video.mp4")
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(video_url) as vid_resp:
                    if vid_resp.status == 200:
                        async with aiofiles.open(video_path, "wb") as f:
                            async for chunk in vid_resp.content.iter_chunked(CHUNK_SIZE):
                                await f.write(chunk)
                        result.media_files.append(MediaFile(file_path=video_path, media_type=MediaType.VIDEO))
                        result.title = "TikTok Video"
                        result.author = "TikTok"
                        result.caption = "Downloaded via Fallback"
                        return result
                        
        return None
