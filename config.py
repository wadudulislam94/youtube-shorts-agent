"""
config.py — Centralized configuration for the YouTube Shorts Agent (Free Edition).

All settings are read from environment variables (via .env file).
Only 2 free API keys are required: Gemini + Pixabay.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Base Paths ────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
OUTPUT_AUDIO   = BASE_DIR / "output" / "audio"
OUTPUT_VIDEO   = BASE_DIR / "output" / "video"
OUTPUT_FINAL   = BASE_DIR / "output" / "final"
ASSETS_FONTS   = BASE_DIR / "assets" / "fonts"
ASSETS_MUSIC   = BASE_DIR / "assets" / "music"
LOGS_DIR       = BASE_DIR / "logs"

# ── API Keys (only 2 required, both free) ─────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
PIXABAY_API_KEY  = os.getenv("PIXABAY_API_KEY", "")
YOUTUBE_API_KEY  = os.getenv("YOUTUBE_API_KEY", "")   # For search — NOT for upload (that uses OAuth)

# ── YouTube OAuth ─────────────────────────────────────────────────────────────
YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "credentials/client_secrets.json")
YOUTUBE_TOKEN_FILE     = os.getenv("YOUTUBE_TOKEN_FILE", "credentials/youtube_token.json")
YOUTUBE_SCOPES         = ["https://www.googleapis.com/auth/youtube.upload"]

# ── TTS Settings (edge-tts — FREE, Microsoft Neural voices) ──────────────────
TTS_VOICE = os.getenv("TTS_VOICE", "random")

# Available Microsoft Neural voices (high quality, completely free)
TTS_VOICES = [
    "en-US-AriaNeural",         # Female, expressive, conversational
    "en-US-ChristopherNeural",  # Male, authoritative, deep
    "en-US-GuyNeural",          # Male, friendly, natural
    "en-US-JennyNeural",        # Female, warm, clear
    "en-GB-RyanNeural",         # British male, engaging
    "en-US-DavisNeural",        # Male, casual, youthful
    "en-US-TonyNeural",         # Male, formal, confident
    "en-AU-NatashaNeural",      # Australian female, upbeat
]

# ── Whisper Settings (local transcription — FREE) ─────────────────────────────
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# ── Content Settings ──────────────────────────────────────────────────────────
CONTENT_NICHE            = os.getenv("CONTENT_NICHE", "art")
SHORTS_PER_RUN           = int(os.getenv("SHORTS_PER_RUN", "1"))
SCHEDULE_INTERVAL_HOURS  = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "6"))

# ── Video Specs (Vertical 9:16 for Shorts) ────────────────────────────────────
VIDEO_WIDTH    = 1080
VIDEO_HEIGHT   = 1920
VIDEO_FPS      = 30
VIDEO_BITRATE  = "8000k"

# ── Subtitle Styling ──────────────────────────────────────────────────────────
SUBTITLE_FONT_NAME       = "Roboto"          # Installed via apt in GitHub Actions
SUBTITLE_FONT_SIZE       = 88
SUBTITLE_FONT_COLOR      = "white"
SUBTITLE_HIGHLIGHT_COLOR = "#FFD700"         # Gold — active word
SUBTITLE_STROKE_COLOR    = "black"
SUBTITLE_STROKE_WIDTH    = 4
SUBTITLE_WORDS_PER_LINE  = 3
SUBTITLE_Y_POSITION      = 0.55             # 0=top, 1=bottom

# ── Niche Configuration ───────────────────────────────────────────────────────
NICHE_CONFIG = {
    "art": {
        "subreddits": [
            "crafts", "oddlysatisfying", "resin",
            "painting", "woodworking", "pottery",
            "DIY", "Art", "drawing",
        ],
        "rss_feeds": [
            "https://feeds.feedburner.com/instructables/categories/craft",
            "https://www.reddit.com/r/crafts/.rss",
        ],
        # Dynamic query — overridden per-video based on topic in video_builder
        "bg_video_query": "satisfying art painting process",
        "tone": "soothing, mesmerizing and inspiring",
        "gemini_persona": "a calming, awe-struck art narrator",
    },
    "facts": {
        "subreddits": ["todayilearned", "interestingasfuck", "coolguides"],
        "rss_feeds": [
            "https://feeds.feedburner.com/LiveScience",
            "https://www.sciencedaily.com/rss/all.xml",
        ],
        "bg_video_query": "satisfying nature abstract",
        "tone": "energetic and mind-blowing",
        "gemini_persona": "a viral science communicator like Kurzgesagt",
    },
    "finance": {
        "subreddits": ["personalfinance", "investing", "financialindependence"],
        "rss_feeds": [
            "https://feeds.finance.yahoo.com/rss/2.0/headline",
            "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        ],
        "bg_video_query": "city skyline night aerial",
        "tone": "authoritative and inspiring",
        "gemini_persona": "a sharp Wall Street insider sharing secrets",
    },
    "motivation": {
        "subreddits": ["GetMotivated", "selfimprovement", "productivity"],
        "rss_feeds": [
            "https://feeds.feedburner.com/tinybuddha",
            "https://jamesclear.com/feed",
        ],
        "bg_video_query": "sunrise mountain landscape cinematic",
        "tone": "passionate and uplifting",
        "gemini_persona": "a high-energy motivational coach like David Goggins",
    },
    "history": {
        "subreddits": ["history", "AskHistorians", "todayilearned"],
        "rss_feeds": [
            "https://www.smithsonianmag.com/rss/history-archaeology/",
            "https://historycollection.com/feed",
        ],
        "bg_video_query": "ancient ruins cinematic drone",
        "tone": "dramatic and storytelling",
        "gemini_persona": "a gripping documentary narrator",
    },
    "tech": {
        "subreddits": ["technology", "Futurology", "artificial"],
        "rss_feeds": [
            "https://feeds.feedburner.com/TechCrunch/",
            "https://www.wired.com/feed/rss",
        ],
        "bg_video_query": "futuristic technology abstract neon",
        "tone": "fast-paced and awe-inspiring",
        "gemini_persona": "a futurist tech journalist breaking big news",
    },
}


def get_niche() -> dict:
    """Return config for the currently selected niche."""
    return NICHE_CONFIG.get(CONTENT_NICHE, NICHE_CONFIG["facts"])
