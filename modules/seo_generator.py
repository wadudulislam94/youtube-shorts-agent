"""
modules/seo_generator.py — Art & Craft Edition
─────────────────────────────────────────────────────────────────────────────
Step 5a: SEO Metadata Generation targeting the Art & Craft niche.
"""

import re
import json
from dataclasses import dataclass, field
from typing import List

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger

log = get_logger("SEOGenerator")

_client = genai.Client(api_key=config.GEMINI_API_KEY)

CATEGORY_IDS = {
    "art":        "26",   # Howto & Style
    "facts":      "27",   # Education
    "finance":    "27",
    "motivation": "22",   # People & Blogs
    "history":    "27",
    "tech":       "28",   # Science & Technology
    "anime":      "24",   # Entertainment
}

# Core art tags always injected
_BASE_ART_TAGS = [
    "shorts", "youtube shorts", "art", "crafts", "diy",
    "satisfying", "artprocess", "craftvideos", "handmade",
    "oddlysatisfying", "asmr", "relaxing", "artshorts",
]

# Core anime tags always injected
_BASE_ANIME_TAGS = [
    "shorts", "youtube shorts", "anime", "animeshorts", "isekai",
    "animestory", "manga", "animefunny", "animemoments", "overpowered",
    "shonen", "animerecommendations", "animenarrative", "isekaianime",
]


@dataclass
class SEOResult:
    title: str
    description: str
    tags: List[str] = field(default_factory=list)
    category_id: str = "26"


_SEO_PROMPT = """You are a YouTube SEO expert specializing in Art, Craft, and Satisfying content.

Generate SEO metadata for this YouTube Short:
Topic: "{topic}"
Script excerpt: "{excerpt}"

The channel is focused on satisfying art creation, craft processes, and DIY.

Return ONLY this JSON (no other text):
{{
  "title": "Viral title under 80 characters. Start with an emoji related to art/craft. Use words like 'Satisfying', 'Mesmerizing', 'Watch', 'How I Made', 'Stunning'. Example: '🎨 Mesmerizing Resin Ocean Pour — Watch This Transform!'",
  "description": "2-3 sentences describing the art process shown. Use the craft keywords naturally. End with: Follow for daily art inspiration! #shorts #art #crafts #satisfying #diy",
  "tags": ["15 to 20 highly searched YouTube tags for art/craft Shorts — mix broad and specific craft terms"]
}}"""


_ANIME_SEO_PROMPT = """You are a YouTube SEO expert specializing in viral Anime Shorts storytelling.
You study the top 0.1% of anime Shorts channels and know exactly what titles get clicks.

Generate SEO metadata for this anime YouTube Short:
Topic: "{topic}"
Script excerpt: "{excerpt}"

The channel posts dramatic anime story Shorts. Each Short is an "episode".
Fans follow to get the NEXT episode. Retention and follows are the main KPIs.

Return ONLY this JSON (no other text):
{{
  "title": "Viral title under 75 characters. Use ONE of these proven viral formats (rotate them, don't always use the same one):\n  - POV format:      'POV: You Reincarnated As The Weakest Hero'\n  - When format:     'When The Trash Hero Speedruns The Demon Lord'\n  - Nobody format:   'Nobody Expected Him To Reach The Final Boss In 3 Minutes'\n  - He/She format:   'He Was Called Trash. Then He Broke The Entire Game'\n  - What If format:  'What If A Gamer Got Isekai'd And Skipped Every Quest'\n  Emoji: rotate from 🔥💫⚡🌀🎯👑🤯✨ — match the mood of the story. No sword emoji every time.",
  "description": "Use the hook sentence from the script as the first line (copy it exactly). Then 1 sentence of story. Then: 'Episode 2 drops soon — follow so you don't miss it!' End with: #shorts #anime #isekai #animeshorts #animestory #overpoweredmc #reincarnation #weakesthero",
  "tags": ["anime", "shorts", "animeshorts", "isekai", "overpowered", "reincarnation", "animestory", "weakesthero", "demonlord", "rpg", "gamer", "animerecommendations", "animeexplained", "shonen", "manhwa", "lightnovel", "animeclips", "animemoments", "animenarrative", "viral"]
}}"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
def generate_seo(topic: str, script: str) -> SEOResult:
    """Generate viral SEO metadata using Gemini. Niche-aware."""
    log.info("Generating SEO metadata...")
    niche = config.CONTENT_NICHE

    if niche == "anime":
        prompt = _ANIME_SEO_PROMPT.format(
            topic=topic,
            excerpt=script[:250].strip(),
        )
    else:
        prompt = _SEO_PROMPT.format(
            topic=topic,
            excerpt=script[:250].strip(),
        )

    response = _client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.85,
            max_output_tokens=512,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON in SEO response: {raw[:200]}")

    parsed = json.loads(json_match.group())
    niche = config.CONTENT_NICHE

    title       = parsed.get("title", topic[:60]).strip()
    description = parsed.get("description", "").strip()
    tags        = parsed.get("tags", [])

    # Enforce length limits
    if len(title) > 100:
        title = title[:97] + "..."

    # Niche-specific hashtag injection
    if niche == "anime":
        if "#shorts" not in description.lower():
            description += "\n\n#shorts #anime #isekai #animeshorts #animestory"
        base_tags = _BASE_ANIME_TAGS
    else:
        if "#shorts" not in description.lower():
            description += "\n\n#shorts #art #crafts #satisfying #diy"
        base_tags = _BASE_ART_TAGS

    # Merge generated tags with base tags, deduplicate
    all_tags = list(dict.fromkeys(base_tags + [t.lower() for t in tags]))[:30]

    result = SEOResult(
        title=title,
        description=description,
        tags=all_tags,
        category_id=CATEGORY_IDS.get(niche, "26"),
    )

    log.info(f"SEO ready: {result.title}")
    log.info(f"Tags ({len(result.tags)}): {', '.join(result.tags[:6])}...")
    return result
