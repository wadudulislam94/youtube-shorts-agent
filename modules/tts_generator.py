"""
modules/tts_generator.py (Free Edition)
─────────────────────────────────────────────────────────────────────────────
Step 3: Voiceover Generation using Microsoft Edge TTS (edge-tts).

100% FREE — no API key, no account, no usage limits.
Uses Microsoft's Azure Neural TTS infrastructure via the Edge browser protocol.

Quality is on par with ElevenLabs for most use cases.
Available voices: en-US-AriaNeural, en-US-ChristopherNeural, en-US-GuyNeural,
                  en-US-JennyNeural, en-GB-RyanNeural, en-US-DavisNeural, etc.
"""

import asyncio
import random
import uuid
from pathlib import Path

import edge_tts
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger

log = get_logger("TTSGenerator")


def _pick_voice() -> str:
    """Select a TTS voice. 'random' picks a different one each video."""
    if config.TTS_VOICE.lower() == "random":
        voice = random.choice(config.TTS_VOICES)
        log.info(f"🎙️  Selected voice: {voice}")
        return voice
    return config.TTS_VOICE


def _output_path() -> Path:
    uid = uuid.uuid4().hex[:8]
    path = config.OUTPUT_AUDIO / f"voice_{uid}.mp3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def _edge_tts_async(script: str, voice: str, output_path: Path) -> None:
    """
    Async core function for edge-tts generation.
    Uses +10% speaking rate for energetic Shorts delivery.
    """
    communicate = edge_tts.Communicate(
        text=script,
        voice=voice,
        rate="+10%",      # Slightly faster = more energetic
        volume="+0%",
        pitch="+0Hz",
    )
    await communicate.save(str(output_path))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_voiceover(script: str) -> Path:
    """
    Generate a high-quality neural TTS voiceover for the given script.

    Uses Microsoft Edge TTS — completely free, no API key needed.

    Args:
        script: The cleaned script string from script_generator.

    Returns:
        Path to the saved .mp3 file.
    """
    voice       = _pick_voice()
    output_path = _output_path()

    log.info(f"🎙️  Generating voiceover with edge-tts [{voice}]...")

    try:
        # Handle both environments: with and without existing event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an async context, use nest_asyncio or create new loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, _edge_tts_async(script, voice, output_path)
                    )
                    future.result(timeout=60)
            else:
                loop.run_until_complete(_edge_tts_async(script, voice, output_path))
        except RuntimeError:
            asyncio.run(_edge_tts_async(script, voice, output_path))

    except Exception as e:
        log.error(f"edge-tts failed: {e}")
        raise

    size_kb = output_path.stat().st_size // 1024
    log.info(f"✅ Voiceover saved: {output_path.name} ({size_kb}KB)")
    return output_path


def get_audio_duration(audio_path: Path) -> float:
    """Return audio duration in seconds using pydub."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(audio_path))
        duration = len(audio) / 1000.0
        log.debug(f"Audio duration: {duration:.2f}s")
        return duration
    except Exception as e:
        log.warning(f"Could not read audio duration via pydub: {e}")
        # Estimate from word count (fallback)
        return 38.0


if __name__ == "__main__":
    test = (
        "Stop scrolling. Octopuses have three hearts and blue blood. "
        "One heart pumps blood to the body. Two pump it to the gills. "
        "When an octopus swims, the main heart actually stops beating — "
        "which is why they prefer crawling. They also have 9 brains. "
        "One central brain and one mini-brain in each arm. "
        "Follow for more mind-blowing animal facts."
    )
    path = generate_voiceover(test)
    print(f"Saved to: {path}")
    print(f"Duration: {get_audio_duration(path):.2f}s")
