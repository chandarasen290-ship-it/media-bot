# 🤖 Telegram Media Downloader Bot (TikTok & Instagram)

A Telegram Bot that automatically downloads and sends videos, photo slideshows, carousels, and stories from **TikTok** and **Instagram** whenever you send or forward a link.

---

## 🌟 Features

- 🎵 **TikTok**:
  - Videos (High Quality, Watermark-Free)
  - Photo Slideshows / Posts (Full image albums sent as Telegram albums + background music audio file)
  - Stories
- 📸 **Instagram**:
  - Reels
  - Posts (Single Photos / Videos)
  - Carousels (Multiple photos and videos delivered in a neat Telegram Media Album)
  - Stories & Highlights (with cookie support)
- ⚡ **Auto-Detection**: Just send or forward any link — no commands needed!
- 🧹 **Zero Disk Clutter**: Temporary files are automatically cleaned up after sending.
- 🐳 **Docker Ready**: One-click deployment with Docker & Docker Compose.

---

## 🚀 Quick Setup Guide

### 1. Get a Telegram Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a name and username for your bot.
3. BotFather will provide you with an **API Token** (e.g., `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`).

---

### 2. Configure the Bot
1. Navigate to the project directory:
   ```bash
   cd telegram-media-downloader-bot
   ```
2. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and paste your `BOT_TOKEN`:
   ```env
   BOT_TOKEN=your_token_from_botfather
   ```

---

### 3. Run the Bot

#### Option A: Run Locally (Python 3.10+)

1. (Recommended) Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate    # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the bot:
   ```bash
   python bot.py
   ```

#### Option B: Run with Docker Compose

```bash
docker compose up -d --build
```
To view logs:
```bash
docker compose logs -f
```

---

## 🍪 How to Enable Instagram / TikTok Stories (Cookies)

Instagram and TikTok require login authentication to view and download stories or content from private accounts you follow.

1. Install a browser extension such as **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)** (available for Chrome, Brave, Firefox).
2. Open [Instagram.com](https://www.instagram.com) in your browser and make sure you are logged in.
3. Click the extension icon and export the cookies as **`cookies.txt`**.
4. Place the `cookies.txt` file in the root directory of this bot:
   ```
   telegram-media-downloader-bot/
   ├── cookies.txt     <--- Place here
   ├── bot.py
   ├── .env
   ...
   ```
5. Restart the bot!

---

## 📁 Project Structure

```
telegram-media-downloader-bot/
├── config.py                 # Configuration loader & validation
├── bot.py                    # Main Telegram bot entrypoint
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── Dockerfile                # Docker container configuration
├── docker-compose.yml        # Docker Compose runner
├── README.md                 # Documentation & setup guide
├── downloader/
│   ├── base.py               # Data models (MediaResult, MediaType, MediaFile)
│   ├── manager.py            # URL router & dispatcher
│   ├── tiktok.py             # TikTok extractor (yt-dlp + TikWM fallback)
│   └── instagram.py          # Instagram extractor (yt-dlp + cookies support)
├── handlers/
│   ├── commands.py           # /start, /help, /status, /cookies
│   └── media.py              # Message listener & Telegram media sender
└── tests/
    └── test_parsers.py       # Unit tests for URL parsers
```

---

## 💡 Telegram Commands

- `/start` - Welcome message and quick instructions.
- `/help` - Supported formats and usage guide.
- `/cookies` - Status of `cookies.txt` and guide on how to set it up.
- `/status` - Check bot status and active settings.
