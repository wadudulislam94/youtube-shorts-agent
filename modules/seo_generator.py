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
}

# Core art tags always injected
_BASE_ART_TAGS = [
    "shorts", "youtube shorts", "art", "crafts", "diy",
    "satisfying", "artprocess", "craftvideos", "handmade",
    "oddlysatisfying", "asmr", "relaxing", "artshorts",
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
def generate_seo(topic: str, script: str) -> SEOResult:
    """Generate viral art/craft SEO metadata using Gemini."""
    log.info("Generating SEO metadata...")

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

    # Ensure art hashtags in description
    if "#shorts" not in description.lower():
        description += "\n\n#shorts #art #crafts #satisfying #diy"

    # Merge generated tags with base art tags, deduplicate
    all_tags = list(dict.fromkeys(_BASE_ART_TAGS + [t.lower() for t in tags]))[:30]

    result = SEOResult(
        title=title,
        description=description,
        tags=all_tags,
        category_id=CATEGORY_IDS.get(niche, "26"),
    )

    log.info(f"SEO ready: {result.title}")
    log.info(f"Tags ({len(result.tags)}): {', '.join(result.tags[:6])}...")
    return result
