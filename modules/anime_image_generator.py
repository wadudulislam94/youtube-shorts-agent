"""
modules/anime_image_generator.py — Anime Art Panel Generator
─────────────────────────────────────────────────────────────────────────────
Generates AI anime-style art panels for each story scene using Pollinations AI.

100% FREE — no API key, no account, no usage limits.
Uses the Pollinations.ai image generation API (backed by Flux / SDXL models).

Each anime Short gets 4 unique scene panels:
  1. Opening establishing shot (world/setting)
  2. Protagonist introduction
  3. Conflict / power reveal
  4. Climax / resolution moment

Image resolution: 1080x1920 (vertical 9:16 for Shorts)
"""

import hashlib
import time
import uuid
from pathlib import Path
from typing import List
from urllib.parse import quote

import requests

import config
from logger import get_logger

log = get_logger("AnimeImageGen")

# ── Pollinations AI endpoint ───────────────────────────────────────────────────
# Free, no API key, no rate limit (reasonable use)
_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

# ── Anime visual style suffix appended to every image prompt ──────────────────
_ANIME_STYLE = (
    "anime art style, detailed anime illustration, cinematic composition, "
    "vibrant colors, dramatic lighting, high quality anime, studio quality, "
    "8k resolution, vertical portrait format 9:16"
)

# ── Scene prompt templates for each story beat ─────────────────────────────────
_SCENE_TEMPLATES = [
    # Scene 1 — Establishing / World
    "{world_prompt}, wide establishing shot, {style}",
    # Scene 2 — Protagonist
    "{hero_prompt}, close-up dramatic portrait, intense expression, {style}",
    # Scene 3 — Conflict / Power reveal
    "{conflict_prompt}, action scene, energy aura, power explosion effect, {style}",
    # Scene 4 — Climax
    "{climax_prompt}, epic moment, cinematic angle, dramatic sky, {style}",
]


def _extract_scene_prompts(topic: str, script: str) -> dict:
    """
    Extract visual prompts for each scene from the story topic and script.
    Falls back to generic anime fantasy prompts if the topic is unclear.
    """
    topic_lower = topic.lower()
    script_lower = script.lower()
    combined = topic_lower + " " + script_lower[:500]

    # ── Detect story type and build scene-specific prompts ────────────────────
    if any(k in combined for k in ["speedrun", "gamer", "rpg", "game", "glitch"]):
        return {
            "world_prompt": "fantasy RPG village with glowing UI elements and quest markers floating in the air",
            "hero_prompt": "young anime gamer with a controller and glowing eyes wearing a hoodie in a fantasy world",
            "conflict_prompt": "anime character phasing through a stone castle wall using a game glitch with pixel artifacts",
            "climax_prompt": "shocked demon lord on a throne watching a casual anime teenager speedrun into his throne room",
        }
    elif any(k in combined for k in ["demon lord", "demon king", "final boss"]):
        return {
            "world_prompt": "dark gothic fantasy castle on a cliff with purple lightning and lava below",
            "hero_prompt": "powerful anime hero with glowing sword standing at the gates of a demon castle",
            "conflict_prompt": "epic clash between a glowing anime hero and a massive dark demon lord with wings",
            "climax_prompt": "anime demon lord defeated, kneeling in ruins, with the hero standing triumphantly",
        }
    elif any(k in combined for k in ["isekai", "reincarnate", "reincarnation", "woke up", "died"]):
        return {
            "world_prompt": "portal of light opening in a lush fantasy world with floating islands and magic ruins",
            "hero_prompt": "confused anime teenager in modern clothes arriving in a magical fantasy world, wide eyes",
            "conflict_prompt": "anime protagonist discovering their hidden magical power, energy burst explosion",
            "climax_prompt": "anime hero standing on a hilltop overlooking a vast fantasy kingdom at sunset",
        }
    elif any(k in combined for k in ["samurai", "sword", "katana", "warrior"]):
        return {
            "world_prompt": "ancient Japan landscape with cherry blossom trees and a misty mountain",
            "hero_prompt": "lone samurai anime warrior with a katana, intense eyes, flowing robes in wind",
            "conflict_prompt": "two samurai clashing swords in slow motion, sparks flying, dramatic anime style",
            "climax_prompt": "victorious samurai sheathing his sword, cherry blossom petals falling around him",
        }
    elif any(k in combined for k in ["chess", "strategy", "mastermind", "genius"]):
        return {
            "world_prompt": "magical chess board as a battlefield with giant animated chess pieces in a fantasy arena",
            "hero_prompt": "anime genius character with glasses smirking at a chess board, glowing aura",
            "conflict_prompt": "anime mastermind making a move on a giant magical chess board that reshapes reality",
            "climax_prompt": "anime strategist winning with a single move, opponents shocked and defeated",
        }
    elif any(k in combined for k in ["magic", "wizard", "mage", "spell", "sorcerer"]):
        return {
            "world_prompt": "magical academy tower in a fantasy world with aurora lights and floating books",
            "hero_prompt": "young anime mage with glowing magical staff, casting a powerful spell",
            "conflict_prompt": "massive magical explosion from an anime sorcerer's forbidden spell in a dark dungeon",
            "climax_prompt": "anime mage standing in the aftermath of a battle, surrounded by light and floating magic runes",
        }
    else:
        # Generic anime fantasy fallback
        return {
            "world_prompt": "vast epic fantasy landscape with mountains, magic ruins, and a dramatic sky",
            "hero_prompt": "powerful anime protagonist with glowing eyes and dramatic wind effect in hair",
            "conflict_prompt": "intense anime battle scene with energy explosions and dramatic lighting",
            "climax_prompt": "victorious anime hero in an epic cinematic pose with a stunning sunset background",
        }


def _build_prompts(topic: str, script: str) -> List[str]:
    """Build 4 anime scene image prompts from topic and script."""
    scenes = _extract_scene_prompts(topic, script)
    prompts = []
    for template in _SCENE_TEMPLATES:
        prompt = template.format(**scenes, style=_ANIME_STYLE)
        prompts.append(prompt)
    return prompts


def _download_image(prompt: str, index: int, seed: int) -> Path:
    """
    Download a single anime image from Pollinations AI.
    Returns the saved Path on success.
    """
    encoded = quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1080&height=1920&seed={seed}&nologo=true&enhance=true"
    )

    dest = config.OUTPUT_VIDEO / f"anime_panel_{index}_{uuid.uuid4().hex[:6]}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"  🎨 Generating anime panel {index+1}/4...")
    log.debug(f"     Prompt: {prompt[:80]}...")

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type:
                log.warning(f"  Unexpected content-type: {content_type}, retrying...")
                time.sleep(3)
                continue

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(65536):
                    if chunk:
                        f.write(chunk)

            size_kb = dest.stat().st_size // 1024
            if size_kb < 10:
                log.warning(f"  Image too small ({size_kb}KB), retrying...")
                dest.unlink(missing_ok=True)
                time.sleep(3)
                continue

            log.info(f"  ✅ Panel {index+1} saved ({size_kb}KB)")
            return dest

        except Exception as e:
            log.warning(f"  Panel {index+1} attempt {attempt+1} failed: {e}")
            time.sleep(5)

    log.error(f"  ❌ Panel {index+1} failed after 3 attempts")
    return None


def generate_anime_panels(topic: str, script: str) -> List[Path]:
    """
    Generate 4 anime-style image panels for the given story.

    Args:
        topic:  Story topic / title string.
        script: Full narration script (used to pick scene-appropriate visuals).

    Returns:
        List of Paths to downloaded .jpg panel images (1080x1920).
        Always returns at least 1 fallback image.
    """
    log.info("🎨 Generating AI anime art panels with Pollinations AI...")

    prompts = _build_prompts(topic, script)

    # Use a topic-based seed for reproducibility + variety across episodes
    base_seed = int(hashlib.md5(topic.encode()).hexdigest()[:8], 16) % 100000

    panels: List[Path] = []
    for i, prompt in enumerate(prompts):
        seed = base_seed + i * 137   # Different seed per panel
        panel = _download_image(prompt, i, seed)
        if panel:
            panels.append(panel)
        time.sleep(1)   # Be polite to the free API

    if not panels:
        log.error("All anime panels failed — pipeline cannot continue without images")
        raise RuntimeError("Failed to generate any anime panels from Pollinations AI")

    log.info(f"✅ {len(panels)}/4 anime panels generated successfully")
    return panels


if __name__ == "__main__":
    # Quick test
    panels = generate_anime_panels(
        topic="A speedrunner dies and reincarnates into a fantasy RPG world",
        script="He died with a controller in his hand. And woke up inside the game.",
    )
    for p in panels:
        print(f"  Panel: {p}")
