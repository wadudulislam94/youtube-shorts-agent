"""
modules/script_generator.py — Art & Craft Edition
─────────────────────────────────────────────────────────────────────────────
Step 2: Script Generation using Google Gemini.

Tone: soothing, mesmerizing, satisfying narrator voice.
Style: trust-the-process art narration — not facts, not news.
"""

import re
import json
from dataclasses import dataclass

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

    def __post_init__(self):
        self.word_count = len(self.full_script.split())
        self.estimated_duration_sec = self.word_count / 2.3


_PROMPT_TEMPLATE = """You are a calming, inspiring narrator for a "satisfying art and craft" YouTube Shorts channel.

Art/Craft Topic: "{topic}"

Write a soothing, engaging voiceover script for a 45-60 second YouTube Short showing this craft being made.

Rules:
- HOOK (2 sentences): Draw the viewer in instantly. Start with something mesmerizing like:
  "Watch what happens when...", "There is something magical about...", "From nothing to breathtaking...",
  "This is how a masterpiece is born...", "Most people have never seen..."
  Do NOT start with "Hey guys", "Welcome", or "In this video".
- BODY (4-5 sentences): Narrate the creation process in present tense. Describe the textures, colors,
  and satisfying moments of making this piece. Make it feel like the viewer is watching it happen live.
  Use sensory language — mention the feel of the material, the colors blending, the satisfying sounds.
- CTA (1 sentence): "Follow for daily art that will make your day better." or "Subscribe — new craft every day."
- TOTAL: 90-120 words. Plain spoken English. No emojis. No hashtags. No asterisks. No markdown.
- Tone: calm, soothing, slightly awe-struck. Like a quiet ASMR narrator watching magic happen.

Return ONLY this JSON (no other text):
{{
  "hook": "string",
  "body": "string",
  "cta": "string"
}}"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
def generate_script(topic: str) -> ScriptResult:
    """Generate a soothing art narration script using Gemini."""
    log.info(f"Writing script for: {topic[:70]}...")

    prompt = _PROMPT_TEMPLATE.format(topic=topic)

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
    log.debug(f"Gemini raw: {raw[:300]}")

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON in Gemini response: {raw[:200]}")

    parsed = json.loads(json_match.group())
    hook = _clean(parsed.get("hook", ""))
    body = _clean(parsed.get("body", ""))
    cta  = _clean(parsed.get("cta", "Follow for daily art inspiration."))

    if not hook or not body:
        raise ValueError(f"Missing hook/body in: {parsed}")

    full_script = f"{hook} {body} {cta}"
    result = ScriptResult(topic=topic, hook=hook, body=body, cta=cta, full_script=full_script)

    log.info(f"Script ready -- {result.word_count} words | ~{result.estimated_duration_sec:.0f}s")
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
    r = generate_script("Pouring resin ocean art with blue and white pigments")
    print(r.full_script)
    print(f"Words: {r.word_count} | ~{r.estimated_duration_sec:.0f}s")
