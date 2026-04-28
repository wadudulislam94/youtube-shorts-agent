"""
modules/script_generator.py — Viral Content Strategist Edition
─────────────────────────────────────────────────────────────────────────────
Step 2: Script Generation.

When a ViralReference with a transcript is available, Gemini acts as a
"Viral Content Strategist" — it analyzes WHY the viral Short worked
(hook, pacing, retention tactics) and writes a brand-new ORIGINAL script
that clones those winning tactics without copying the content.

When no transcript is available, falls back to the soothing art narrator mode.
"""

import re
import json
from dataclasses import dataclass
from typing import Union

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger

log = get_logger("ScriptGenerator")

_client = genai.Client(api_key=config.GEMINI_API_KEY)


@dataclass
class ScriptResult:
    topic: str
    hook: str
    body: str
    cta: str
    full_script: str
    word_count: int = 0
    estimated_duration_sec: float = 0.0
    strategy_used: str = "standard"   # "viral_clone" | "standard"

    def __post_init__(self):
        self.word_count = len(self.full_script.split())
        self.estimated_duration_sec = self.word_count / 2.3


# ── Viral Clone Prompt (used when we have a real viral reference) ──────────────

_VIRAL_PROMPT = """You are a Viral Content Strategist for a YouTube Shorts channel about satisfying art & craft.

I found a real viral YouTube Short that got millions of views. Your job is to:
1. Analyze WHY it went viral (the hook, pacing, emotional triggers, retention tactics)
2. Write a completely NEW, ORIGINAL script that uses the SAME psychological tactics

═══════════════════════════════════════════════════════
VIRAL REFERENCE (DO NOT COPY — ANALYZE ONLY):
{viral_context}
═══════════════════════════════════════════════════════

YOUR ANALYSIS TASK:
- What makes the hook irresistible? (curiosity gap, visual promise, emotional trigger?)
- What's the pacing? (fast cuts? slow reveal? transformation?)
- What retention tactic keeps people watching? (before/after? process reveal? "wait for it"?)
- What emotional payoff does the viewer get? (satisfying, awe, calming?)

YOUR WRITING TASK:
Write a brand-new 45-60 second voiceover script for a SHORT about THIS topic: "{topic}"
Use the SAME hook style, pacing, and retention tactics as the viral reference.
The script must be 100% original — different topic, different words, same viral formula.

Rules:
- HOOK (2 sentences): Copy the EMOTIONAL STRUCTURE of the viral hook, not the words.
  Make the viewer NEED to keep watching.
- BODY (4-5 sentences): Mirror the pacing. If the viral was fast, be punchy. If slow, be soothing.
  Describe the art/craft process in a way that matches what made the viral video irresistible.
- CTA (1 sentence): "Follow for more" or "Subscribe for daily art."
- Total: 90-120 words. Plain spoken English. No hashtags. No asterisks. No markdown. No emojis.

Return ONLY this JSON (no other text):
{{
  "hook": "string",
  "body": "string",
  "cta": "string",
  "viral_tactics_used": "1-sentence summary of what viral tactics you applied"
}}"""



# ── Standard Narrator Prompt (fallback when no viral reference) ────────────────

_STANDARD_PROMPT = """You are a calming, inspiring narrator for a "satisfying art and craft" YouTube Shorts channel.

Art/Craft Topic: "{topic}"

Write a soothing, engaging voiceover script for a 45-60 second YouTube Short.

Rules:
- HOOK (2 sentences): Draw the viewer in instantly. Start with something mesmerizing like:
  "Watch what happens when...", "There is something magical about...", "From nothing to breathtaking..."
  Do NOT start with "Hey guys", "Welcome", or "In this video".
- BODY (4-5 sentences): Narrate the creation process in present tense. Use sensory language —
  textures, colors blending, satisfying sounds. Make it feel live.
- CTA (1 sentence): "Follow for daily art inspiration." or "Subscribe — new craft every day."
- Total: 90-120 words. Plain spoken English. No hashtags. No asterisks. No markdown. No emojis.
- Tone: calm, soothing, slightly awe-struck. Like a quiet ASMR narrator.

Return ONLY this JSON (no other text):
{{
  "hook": "string",
  "body": "string",
  "cta": "string"
}}"""


# ── Anime Story Prompt ────────────────────────────────────────────────────────

_ANIME_PROMPT = """You are the #1 viral anime short-form storyteller on YouTube.
Your Shorts get 1M-10M views because you understand EXACTLY what makes
someone stop scrolling, watch twice, and smash follow.

Anime Story Concept: "{topic}"

Write a 60-70 second narration using these PROVEN viral formulas:

════════════════════════════════════════════════════════
HOOK (FIRST 3 SECONDS — THE MOST CRITICAL PART):
  Use ONE of these and make it EXPLOSIVE:
  A) POV:      "POV: You just died. The system gave you one last power."
  B) Question: "What if the weakest class was actually the most broken?"
  C) Stakes:   "He had 60 seconds to defeat the Demon Lord. Clock starts now."
  D) Twist:    "Everyone called him trash. They never saw what came next."
  E) Shock:    "He speedran the entire dungeon in 47 seconds. S-ranks were furious."

  Hook RULES (non-negotiable):
  - Max 2 short sentences
  - Create an INFORMATION GAP - viewer MUST watch to find the answer
  - Use "he", "she", "you" - make it feel personal
  - End on unresolved tension. No resolution in the hook.

STORY BODY (6-8 SENTENCES - BUILD THE TENSION):
  - Present tense, fast-cut style narrator voice
  - Beat 1: Establish the underdog or impossible situation
  - Beat 2: The first obstacle - it looks hopeless
  - Beat 3: THE POWER REVEAL - the shocking ability awakens
  - Beat 4: Consequences cascade - everything changes
  - Beat 5: One final shock or twist that reframes everything
  - Use sentence fragments for pace: "He runs. Guards appear. He escapes."
  - Every sentence must ESCALATE: weaker to stronger to UNSTOPPABLE

CLIFFHANGER CTA (1 SENTENCE - CRITICAL FOR FOLLOWS):
  Give a REASON to follow, not just "subscribe".
  Examples:
  - "But the Demon Lord had one last card. Nobody expected what it was."
  - "Episode 2 is where it gets truly insane. Follow before it drops."
  - "The story behind HOW he got that power changes everything. Follow now."
  NEVER say: "subscribe for more" or generic "follow for more content"
════════════════════════════════════════════════════════

STRICT RULES:
- 130-160 words total. Every word earns its place.
- Max 12 words per sentence. Shorter = more impact.
- PERFECT ENGLISH GRAMMAR. Re-read your output. Fix any errors before returning.
- No hashtags. No asterisks. No markdown. No emojis in script body.
- Present tense throughout the story.
- Hook must end mid-tension - the viewer MUST keep watching.

Return ONLY this JSON (no other text):
{{
  "hook": "string - explosive 1-2 sentence opener only",
  "body": "string - the 6-8 sentence escalating story",
  "cta": "string - cliffhanger with a real reason to follow"
}}"""


# ── Main Generator ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
def generate_script(topic_or_ref) -> ScriptResult:
    """
    Generate a script. Accepts either:
    - A ViralReference object (uses Viral Content Strategist prompt)
    - A plain string topic (uses standard narrator prompt)
    """
    # Import here to avoid circular imports
    from modules.trend_finder import ViralReference

    topic = str(topic_or_ref)
    niche = config.CONTENT_NICHE

    # Decide which prompt to use
    if niche == "anime":
        strategy = "anime_story"
        prompt = _ANIME_PROMPT.format(topic=topic)
        log.info(f"⚔️  Anime narrator mode — {topic[:60]}")
    elif isinstance(topic_or_ref, ViralReference) and topic_or_ref.source == "youtube_viral":
        strategy = "viral_clone"
        viral_context = topic_or_ref.viral_context_for_gemini()
        prompt = _VIRAL_PROMPT.format(
            viral_context=viral_context,
            topic=topic,
        )
        log.info(f"🔥 Viral strategist mode | {topic_or_ref.views:,} views reference")
    else:
        strategy = "standard"
        prompt = _STANDARD_PROMPT.format(topic=topic)
        log.info(f"🎨 Standard narrator mode")

    log.info(f"Writing script for: {topic[:70]}...")

    response = _client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.9,
            max_output_tokens=600,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    log.debug(f"Gemini raw: {raw[:300]}")

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON in Gemini response: {raw[:200]}")

    parsed = json.loads(json_match.group())
    hook = _clean(parsed.get("hook", ""))
    body = _clean(parsed.get("body", ""))
    cta  = _clean(parsed.get("cta", "Follow for daily art inspiration."))

    # Log the viral tactics used (for debugging)
    if strategy == "viral_clone" and parsed.get("viral_tactics_used"):
        log.info(f"💡 Tactics: {parsed['viral_tactics_used']}")

    if not hook or not body:
        raise ValueError(f"Missing hook/body in: {parsed}")

    full_script = f"{hook} {body} {cta}"
    result = ScriptResult(
        topic=topic,
        hook=hook,
        body=body,
        cta=cta,
        full_script=full_script,
        strategy_used=strategy,
    )

    log.info(f"Script ready [{strategy}] — {result.word_count} words | ~{result.estimated_duration_sec:.0f}s")
    return result


def _clean(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'_+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'#\w+', '', text)
    emoji_re = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0]+", flags=re.UNICODE)
    text = emoji_re.sub('', text)
    return re.sub(r'\s+', ' ', text).strip()


if __name__ == "__main__":
    # Quick test with a plain string
    r = generate_script("Pouring resin ocean art with blue and white pigments")
    print(r.full_script)
    print(f"Strategy: {r.strategy_used} | Words: {r.word_count} | ~{r.estimated_duration_sec:.0f}s")
