"""
modules/trend_finder.py — Art & Craft Edition
─────────────────────────────────────────────────────────────────────────────
Step 1: Topic Discovery focused on Craft, Art, and Satisfying DIY content.

Sources (tried in priority order):
  1. Reddit public JSON — r/crafts, r/oddlysatisfying, r/resin, etc.
  2. RSS feeds          — art & craft blogs/communities
  3. Evergreen fallback — curated craft project ideas (always works)
"""

import random
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger

log = get_logger("TrendFinder")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YouTubeShortsAgent/2.0; +research)",
    "Accept": "application/json, text/xml, */*",
}


# ── Reddit Public JSON (no API key needed) ────────────────────────────────────

def _fetch_reddit(niche_cfg: dict) -> Optional[str]:
    """Use Reddit's public .json endpoint — no credentials required."""
    subreddits = niche_cfg.get("subreddits", ["crafts"])
    subreddit  = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=30"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]

        candidates = [
            p["data"]["title"]
            for p in posts
            if p["data"].get("score", 0) > 200
            and not p["data"].get("stickied", False)
            and not p["data"].get("distinguished")
            and 20 < len(p["data"]["title"]) < 200
            and not p["data"]["title"].lower().startswith("weekly")
            and not p["data"]["title"].lower().startswith("megathread")
        ]

        if candidates:
            topic = random.choice(candidates[:12])
            # Clean up Reddit-isms
            topic = re.sub(r'^\[OC\]\s*', '', topic, flags=re.IGNORECASE).strip()
            topic = re.sub(r'^\[.\]\s*', '', topic).strip()
            log.info(f"📌 Reddit ({subreddit}): {topic[:80]}...")
            return _craft_topic_from_title(topic, subreddit)

    except Exception as e:
        log.warning(f"Reddit fetch failed ({subreddit}): {e}")

    return None


def _craft_topic_from_title(title: str, subreddit: str) -> str:
    """Convert a Reddit post title into a usable craft topic."""
    # If it already sounds like a craft description, use it
    craft_keywords = [
        "resin", "pour", "paint", "clay", "pottery", "wood", "carv",
        "knit", "crochet", "embroider", "sew", "weav", "glaze", "mosaic",
        "sculpt", "sketch", "watercolor", "acrylic", "oil paint", "origami",
        "macrame", "candle", "soap", "jewelry", "bead", "felt", "quilt",
        "block print", "linocut", "engrav", "burn", "leather", "glass",
    ]
    if any(kw in title.lower() for kw in craft_keywords):
        return title

    # Otherwise generate a craft topic from the subreddit context
    fallbacks_by_sub = {
        "oddlysatisfying": _random_satisfying_craft(),
        "crafts": _random_craft_project(),
        "resin": _random_resin_project(),
        "painting": _random_painting_project(),
        "woodworking": _random_woodworking_project(),
        "pottery": _random_pottery_project(),
    }
    return fallbacks_by_sub.get(subreddit, title)


# ── RSS Feeds (no API key needed) ─────────────────────────────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
def _fetch_rss(niche_cfg: dict) -> Optional[str]:
    """Parse an art/craft RSS feed and extract a topic."""
    feeds = niche_cfg.get("rss_feeds", [])
    if not feeds:
        return None

    feed_url = random.choice(feeds)

    try:
        resp = requests.get(feed_url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        titles = []

        for item in root.findall(".//item"):
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                titles.append(title_el.text.strip())

        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            if title_el is not None and title_el.text:
                titles.append(title_el.text.strip())

        good = [t for t in titles if 20 < len(t) < 180 and not t.startswith("<")]

        if good:
            topic = random.choice(good[:10])
            log.info(f"📰 RSS feed: {topic[:80]}...")
            return topic

    except Exception as e:
        log.warning(f"RSS fetch failed ({feed_url}): {e}")

    return None


# ── Craft Topic Generators ─────────────────────────────────────────────────────

def _random_satisfying_craft() -> str:
    return random.choice([
        "Satisfying resin ocean wave pour with blue and white pigment",
        "Hypnotic acrylic paint pour creating a galaxy marble effect",
        "Satisfying kinetic sand cutting and shaping process",
        "Oddly satisfying pottery wheel shaping a perfect vase",
        "Mesmerizing fluid art — cells forming with silicone oil",
    ])

def _random_craft_project() -> str:
    return random.choice([
        "Turning a plain canvas into a stunning abstract painting",
        "Making a hand-stamped leather wallet from scratch",
        "Creating a macrame wall hanging with natural cotton rope",
        "Hand-painting intricate patterns on river stones",
        "Building a miniature terrarium inside a glass bottle",
    ])

def _random_resin_project() -> str:
    return random.choice([
        "Casting a glowing river table with blue epoxy resin",
        "Pouring clear resin over pressed wildflowers in a tray",
        "Making a resin ocean art piece with real sand and shells",
        "Creating a geode-inspired resin coaster with gold leaf",
        "Casting a translucent resin chessboard with embedded art",
    ])

def _random_painting_project() -> str:
    return random.choice([
        "Painting a misty mountain landscape in one hour with acrylics",
        "Watercolor cherry blossom tree painted in real time",
        "Bob Ross style happy little trees painted with a palette knife",
        "One-stroke rose technique creating a stunning floral canvas",
        "Speed painting a hyperrealistic portrait with oil paints",
    ])

def _random_woodworking_project() -> str:
    return random.choice([
        "Carving a beautiful spoon from a raw piece of cherry wood",
        "Building a floating walnut shelf with hidden iron brackets",
        "Turning a plain wooden bowl on a lathe start to finish",
        "Crafting an intricate inlaid cutting board with maple and walnut",
        "Making a hand-carved wooden jewelry box with a hidden compartment",
    ])

def _random_pottery_project() -> str:
    return random.choice([
        "Throwing a perfect tea bowl on the pottery wheel",
        "Hand-building a rustic ceramic planter with textured walls",
        "Glazing a porcelain mug with a cosmic blue dip-glaze",
        "Pulling walls on a large vase from a centered clay mound",
        "Firing handmade ceramic tiles in a raku kiln",
    ])


# ── Evergreen Fallback (always works, no internet needed) ─────────────────────

FALLBACK_TOPICS = {
    "art": [
        "Pouring mesmerizing resin ocean art with blue and white pigments",
        "Creating a stunning galaxy painting with acrylic pour technique",
        "Hand-throwing a perfect clay bowl on the pottery wheel",
        "Painting a misty forest landscape with wet-on-wet watercolor",
        "Carving intricate patterns into a block of white clay",
        "Building a glowing epoxy river table with live-edge wood",
        "Weaving a colorful macrame plant hanger from scratch",
        "Speed painting a photorealistic eye with colored pencils",
        "Making handmade soap with swirling natural pigments",
        "Cutting and polishing a raw amethyst crystal into a gemstone",
        "Block printing a botanical pattern on linen fabric",
        "Creating a stained glass sun-catcher with copper foil technique",
        "Sculpting a lifelike animal from air-dry clay",
        "Making a hand-bound leather journal from scratch",
        "Casting a glowing resin geode coaster with gold leaf veins",
    ],
    "facts": [  # fallback for other niches
        "Pouring mesmerizing resin ocean art with blue and white pigments",
        "Creating a galaxy painting with acrylic pour technique",
        "Hand-throwing a perfect clay bowl on the pottery wheel",
    ],
}


def _fallback(niche: str) -> str:
    topics = FALLBACK_TOPICS.get(niche, FALLBACK_TOPICS["art"])
    topic = random.choice(topics)
    log.info(f"🔒 Fallback topic: {topic[:80]}...")
    return topic


# ── Public Interface ───────────────────────────────────────────────────────────

def discover_topic() -> str:
    """
    Discover a craft/art topic. Tries Reddit → RSS → Fallback.
    Always returns a string, never raises.
    """
    niche     = config.CONTENT_NICHE
    niche_cfg = config.get_niche()

    log.info(f"🔍 Discovering topic for niche: [{niche}]")

    topic = _fetch_reddit(niche_cfg)
    if topic:
        return topic

    try:
        topic = _fetch_rss(niche_cfg)
        if topic:
            return topic
    except Exception as e:
        log.warning(f"RSS error: {e}")

    return _fallback(niche)


if __name__ == "__main__":
    print(discover_topic())
