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


_ANIME_SEO_PROMPT = """You are a YouTube SEO expert specializing in viral Anime Shorts.
You study top anime channels with 1M+ subscribers and know exactly what titles get clicks.

Generate SEO metadata for this anime YouTube Short:
Topic: "{topic}"
Script excerpt: "{excerpt}"

The channel posts dramatic anime story Shorts. Each video is a self-contained episode.

RETURN VALID JSON. Titles MUST be grammatically correct, natural English.

Return ONLY this JSON (no other text):
{{
  "title": "Viral title under 70 characters. MUST use ONE of these proven formats:\n  - 'POV: You Reincarnated As The Weakest Hero' (POV format)\n  - 'When The Trash Hero Speedruns The Demon Lord' (When format)\n  - 'Nobody Expected Him To Break The Entire Game' (Nobody format)\n  - 'He Was Called Trash. Then He Rewrote History.' (He/She format)\n  - 'What If A Gamer Got Isekai'd And Broke Every Rule' (What If format)\n  MANDATORY: Read the title out loud. If it sounds wrong or unnatural, rewrite it.\n  Emoji: pick from 🔥💫⚡🌀🎯👑🤯✨ — match the story mood.",
  "description": "First line: copy the hook sentence from the script exactly. Second line: 1 sentence teasing what happens. Third line: 'New episode dropping soon — follow so you don't miss it!' End with: #shorts #anime #isekai #animeshorts #animestory #overpoweredmc #weakesthero #shonen",
  "tags": ["anime", "shorts", "animeshorts", "isekai", "overpowered", "reincarnation", "animestory", "weakesthero", "demonlord", "rpg", "gamer", "animerecommendations", "animeexplained", "shonen", "manhwa", "lightnovel", "animeclips", "animemoments", "animenarrative", "viral"]
}}"""


# ── Title Quality Gate ─────────────────────────────────────────────────────────

_ANIME_TITLE_TEMPLATES = [
    "POV: You Woke Up As The Strongest Being Alive",
    "Nobody Expected Him To Defeat The Demon Lord This Fast",
    "He Was Called Trash. Then He Broke The Game.",
    "When The Weakest Hero Speedruns The Final Dungeon",
    "What If A Gamer Got Isekai'd And Skipped Every Quest",
    "He Had 60 Seconds To Win. The World Watched.",
    "They Called Him Zero. He Became The Only One.",
]

def _validate_title(title: str, topic: str, niche: str) -> str:
    """
    Basic sanity check on AI-generated titles.
    Rejects titles that are clearly broken and substitutes a template.
    """
    if not title or len(title) < 15:
        log.warning(f"Title too short, using fallback: '{title}'")
        return _fallback_title(topic, niche)

    # Check for obvious word-level errors (common AI hallucinations)
    suspicious = ["merts", "mert", "skys", "beautifull", "achivement", "strentgh"]
    title_lower = title.lower()
    for bad in suspicious:
        if bad in title_lower:
            log.warning(f"Bad grammar detected in title ('{bad}'), using fallback: '{title}'")
            return _fallback_title(topic, niche)

    # Check title doesn't end mid-word (truncation artifact)
    if title[-1].isalpha() and len(title) > 65:
        log.warning(f"Title may be truncated: '{title}'")

    return title


def _fallback_title(topic: str, niche: str) -> str:
    """Generate a safe, grammatically correct fallback title."""
    import random
    if niche == "anime":
        return random.choice(_ANIME_TITLE_TEMPLATES)
    # Generic fallback
    words = topic.split()[:6]
    return "Watch What Happens When " + " ".join(words).title()


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
        model="gemini-2.0-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.75,
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

    # Grammar quality gate — reject titles that look broken/unnatural
    title = _validate_title(title, topic, niche)

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
