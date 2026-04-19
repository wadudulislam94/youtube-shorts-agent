"""
modules/trend_finder.py — Viral-First Edition
─────────────────────────────────────────────────────────────────────────────
Step 1: Topic Discovery by analyzing REAL viral YouTube Shorts.

Strategy:
  1. Search YouTube Data API for recent Shorts (last 30 days) in the art niche
  2. Rank by view count — pick from the top 10
  3. Fetch the transcript of that viral Short using youtube-transcript-api
  4. Return a ViralReference object containing all metadata + transcript

Fallback chain: YouTube API → Reddit → Evergreen list
"""

import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger

log = get_logger("TrendFinder")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YouTubeShortsAgent/3.0)",
    "Accept": "application/json",
}


# ── ViralReference — returned by discover_topic() ─────────────────────────────

@dataclass
class ViralReference:
    """Holds data about a real viral Short that we're modelling after."""
    topic: str                      # Human-readable topic name (for logs/SEO)
    title: str = ""                 # Original viral video title
    views: int = 0                  # View count
    likes: int = 0                  # Like count
    description: str = ""          # Original video description
    transcript: str = ""           # Full transcript text (if available)
    video_id: str = ""             # YouTube video ID (for reference)
    source: str = "fallback"       # "youtube_viral" | "reddit" | "fallback"

    def __str__(self) -> str:
        """Make this behave as a string so main.py works without changes."""
        return self.topic

    def has_transcript(self) -> bool:
        return bool(self.transcript and len(self.transcript.strip()) > 50)

    def viral_context_for_gemini(self) -> str:
        """Build a rich context block to pass to Gemini."""
        lines = [f'Viral Video Title: "{self.title}"']
        if self.views:
            lines.append(f"Views: {self.views:,} | Likes: {self.likes:,}")
        if self.has_transcript():
            # Trim transcript to ~1500 chars to stay in token budget
            transcript_snippet = self.transcript[:1500].strip()
            lines.append(f"\nTranscript:\n{transcript_snippet}")
        elif self.description:
            lines.append(f"\nDescription: {self.description[:500]}")
        return "\n".join(lines)


# ── YouTube Data API Search ────────────────────────────────────────────────────

# Art/craft niche search queries — rotated to find different viral content
_VIRAL_SEARCH_QUERIES = {
    "art": [
        "satisfying resin art #shorts",
        "pottery wheel satisfying #shorts",
        "acrylic pour painting #shorts",
        "satisfying art process #shorts",
        "woodworking satisfying #shorts",
        "clay sculpting satisfying #shorts",
        "watercolor painting timelapse #shorts",
        "satisfying craft making #shorts",
        "oddly satisfying art #shorts",
        "resin pour satisfying #shorts",
    ],
    "facts":       ["mind blowing facts #shorts", "did you know facts #shorts"],
    "finance":     ["money tips #shorts", "financial advice #shorts"],
    "motivation":  ["motivation #shorts", "mindset advice #shorts"],
    "history":     ["history facts #shorts", "historical moments #shorts"],
    "tech":        ["tech facts #shorts", "AI technology #shorts"],
}


def _youtube_search_viral(niche: str) -> Optional[ViralReference]:
    """
    Search YouTube Data API for viral Shorts published in the last 30 days.
    Returns a ViralReference for the most-viewed result, or None on failure.
    """
    api_key = config.YOUTUBE_API_KEY
    if not api_key:
        log.warning("YOUTUBE_API_KEY not set — skipping YouTube viral search")
        return None

    queries = _VIRAL_SEARCH_QUERIES.get(niche, _VIRAL_SEARCH_QUERIES["art"])
    query   = random.choice(queries)

    # Only look at videos from the last 30 days
    published_after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    try:
        # Step 1: Search for Shorts
        search_url = "https://www.googleapis.com/youtube/v3/search"
        search_params = {
            "part":           "snippet",
            "q":              query,
            "type":           "video",
            "videoDuration":  "short",   # <= 4 minutes (catches Shorts)
            "order":          "viewCount",
            "publishedAfter": published_after,
            "maxResults":     15,
            "key":            api_key,
        }
        resp = requests.get(search_url, params=search_params, timeout=12)
        resp.raise_for_status()
        items = resp.json().get("items", [])

        if not items:
            log.warning(f"No YouTube results for query: {query}")
            return None

        # Step 2: Get view/like stats for these videos
        video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
        stats_url = "https://www.googleapis.com/youtube/v3/videos"
        stats_params = {
            "part": "statistics,snippet",
            "id":   ",".join(video_ids),
            "key":  api_key,
        }
        stats_resp = requests.get(stats_url, params=stats_params, timeout=12)
        stats_resp.raise_for_status()
        stats_items = stats_resp.json().get("items", [])

        # Sort by view count descending
        def get_views(item):
            return int(item.get("statistics", {}).get("viewCount", 0))

        stats_items.sort(key=get_views, reverse=True)

        # Pick randomly from top 5 to add variety
        top_items = stats_items[:5]
        if not top_items:
            return None

        chosen = random.choice(top_items)
        video_id   = chosen["id"]
        snippet    = chosen.get("snippet", {})
        statistics = chosen.get("statistics", {})

        title       = snippet.get("title", "")
        description = snippet.get("description", "")[:500]
        views       = int(statistics.get("viewCount", 0))
        likes       = int(statistics.get("likeCount", 0))

        log.info(f"🔥 Viral Short found: '{title[:60]}' — {views:,} views")

        # Step 3: Fetch transcript
        transcript = _fetch_transcript(video_id)

        # Build topic string (cleaned title for use as topic)
        topic = _clean_title_to_topic(title)

        return ViralReference(
            topic=topic,
            title=title,
            views=views,
            likes=likes,
            description=description,
            transcript=transcript,
            video_id=video_id,
            source="youtube_viral",
        )

    except Exception as e:
        log.warning(f"YouTube viral search failed: {e}")
        return None


def _fetch_transcript(video_id: str) -> str:
    """
    Fetch transcript for a YouTube video using youtube-transcript-api.
    Returns empty string if not available.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        full_text = " ".join(entry["text"] for entry in transcript_list)
        log.info(f"📝 Transcript fetched: {len(full_text)} chars")
        return full_text
    except ImportError:
        log.warning("youtube-transcript-api not installed — run: pip install youtube-transcript-api")
        return ""
    except Exception as e:
        log.info(f"No transcript available for {video_id}: {type(e).__name__}")
        return ""


def _clean_title_to_topic(title: str) -> str:
    """Strip hashtags, emojis, and junk from YouTube titles to get a clean topic."""
    title = re.sub(r'#\w+', '', title)
    emoji_re = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0]+", flags=re.UNICODE)
    title = emoji_re.sub('', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title if len(title) > 10 else "Satisfying art creation process"


# ── Reddit Fallback ────────────────────────────────────────────────────────────

_ART_SUBREDDITS = [
    "crafts", "oddlysatisfying", "resin", "painting",
    "woodworking", "pottery", "DIY", "Art", "drawing",
]

def _fetch_reddit_fallback(niche: str) -> Optional[ViralReference]:
    """Reddit-based topic discovery as fallback."""
    niche_cfg  = config.get_niche()
    subreddits = niche_cfg.get("subreddits", _ART_SUBREDDITS)
    subreddit  = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]

        candidates = [
            p["data"]["title"]
            for p in posts
            if p["data"].get("score", 0) > 100
            and not p["data"].get("stickied")
            and 15 < len(p["data"]["title"]) < 150
        ]

        if candidates:
            title = random.choice(candidates[:10])
            title = re.sub(r'^\[OC\]\s*', '', title, flags=re.IGNORECASE).strip()
            topic = _clean_title_to_topic(title)
            log.info(f"📌 Reddit fallback ({subreddit}): {topic[:70]}...")
            return ViralReference(
                topic=topic,
                title=title,
                source="reddit",
            )
    except Exception as e:
        log.warning(f"Reddit fallback failed: {e}")
    return None


# ── Evergreen Fallback ─────────────────────────────────────────────────────────

_FALLBACK_TOPICS = [
    "Pouring mesmerizing resin ocean art with blue and white pigments",
    "Throwing a perfect clay bowl on the pottery wheel",
    "Painting a misty mountain landscape with wet-on-wet watercolor",
    "Carving intricate patterns into a live-edge wood slab",
    "Building a glowing epoxy river table with blue resin",
    "Weaving a colorful macrame wall hanging from scratch",
    "Speed painting a photorealistic eye with colored pencils",
    "Creating a stained glass sun-catcher with copper foil technique",
    "Sculpting a lifelike animal from air-dry clay",
    "Casting a glowing resin geode coaster with gold leaf veins",
]

def _evergreen_fallback() -> ViralReference:
    topic = random.choice(_FALLBACK_TOPICS)
    log.info(f"🔒 Evergreen fallback: {topic[:70]}...")
    return ViralReference(topic=topic, title=topic, source="fallback")


# ── Public Interface ───────────────────────────────────────────────────────────

def discover_topic() -> ViralReference:
    """
    Discover a viral topic. Tries:
      1. YouTube viral search (finds real high-view Shorts + transcript)
      2. Reddit hot posts
      3. Evergreen fallback (always works)

    Returns a ViralReference. Use str(result) to get the topic string.
    """
    niche = config.CONTENT_NICHE
    log.info(f"🔍 Discovering viral topic for niche: [{niche}]")

    # 1. YouTube viral search (primary)
    ref = _youtube_search_viral(niche)
    if ref:
        return ref

    # 2. Reddit hot posts (secondary)
    ref = _fetch_reddit_fallback(niche)
    if ref:
        return ref

    # 3. Evergreen fallback (always works)
    return _evergreen_fallback()


if __name__ == "__main__":
    ref = discover_topic()
    print(f"\nTopic: {ref.topic}")
    print(f"Source: {ref.source}")
    print(f"Views: {ref.views:,}")
    if ref.has_transcript():
        print(f"Transcript ({len(ref.transcript)} chars): {ref.transcript[:200]}...")
