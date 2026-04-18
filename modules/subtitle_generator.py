"""
modules/subtitle_generator.py (Free Edition)
─────────────────────────────────────────────────────────────────────────────
Step 4a: Word-Level Timestamp Generation using faster-whisper (local AI).

100% FREE — runs entirely on your CPU, no API key, no internet needed.
Downloads the Whisper model (~74MB for 'base') on first run.

faster-whisper is 4x faster than openai-whisper with lower memory usage.
Word-level timestamps are precise and reliable.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import config
from logger import get_logger

log = get_logger("SubtitleGenerator")


@dataclass
class WordTimestamp:
    word: str
    start: float   # seconds
    end: float     # seconds


@dataclass
class SubtitleChunk:
    """A group of words displayed together, with one word highlighted."""
    words: List[WordTimestamp]
    start: float
    end: float
    text: str           # combined display text
    active_idx: int = 0 # which word index is currently spoken


# ── faster-whisper transcription ──────────────────────────────────────────────

_whisper_model = None  # Lazy-loaded singleton


def _get_model():
    """Load the Whisper model once and cache it."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = config.WHISPER_MODEL

        log.info(f"🤖 Loading Whisper model [{model_size}] — first run downloads ~74MB...")
        _whisper_model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",   # Fastest on CPU
            download_root=str(config.BASE_DIR / "assets" / "whisper_models"),
        )
        log.info(f"✅ Whisper [{model_size}] model loaded.")
    return _whisper_model


def _transcribe_with_whisper(audio_path: Path) -> List[WordTimestamp]:
    """
    Transcribe audio with faster-whisper and extract per-word timestamps.
    """
    log.info("🔤 Transcribing audio with local Whisper model...")
    t0 = time.time()

    model = _get_model()

    segments, info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language="en",
        beam_size=5,
        vad_filter=True,           # Skip silent sections
        vad_parameters={
            "min_silence_duration_ms": 300,
        },
    )

    word_timestamps = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                clean_word = w.word.strip().strip(".,!?;:'\"").strip()
                if clean_word:
                    word_timestamps.append(WordTimestamp(
                        word=clean_word,
                        start=w.start,
                        end=w.end,
                    ))

    elapsed = time.time() - t0
    log.info(f"✅ Whisper extracted {len(word_timestamps)} words in {elapsed:.1f}s")
    return word_timestamps


# ── Fallback: evenly-distributed timestamps ───────────────────────────────────

def _distribute_timestamps(script: str, duration: float) -> List[WordTimestamp]:
    """
    When Whisper fails, distribute words evenly across the duration.
    Not perfect for highlighting but always works as a backup.
    """
    log.warning("Using fallback evenly-distributed word timestamps.")
    words = [w.strip(".,!?;:'\"") for w in script.split() if w.strip()]
    n = len(words)
    if n == 0:
        return []

    interval = duration / n
    return [
        WordTimestamp(
            word=words[i],
            start=i * interval,
            end=(i + 1) * interval,
        )
        for i in range(n)
    ]


# ── Chunking ──────────────────────────────────────────────────────────────────

def _build_chunks(
    words: List[WordTimestamp],
    words_per_chunk: int = 3,
) -> List[SubtitleChunk]:
    """
    Group words into SubtitleChunks of N words each.
    Each word within the chunk gets its own active moment for karaoke effect.
    """
    chunks: List[SubtitleChunk] = []

    for i in range(0, len(words), words_per_chunk):
        group = words[i : i + words_per_chunk]
        if not group:
            continue

        group_text = " ".join(w.word for w in group)

        # One SubtitleChunk entry per word in the group (for highlight animation)
        for j, active_word in enumerate(group):
            chunks.append(SubtitleChunk(
                words=group,
                start=active_word.start,
                end=active_word.end,
                text=group_text,
                active_idx=j,
            ))

    return chunks


# ── Public Interface ───────────────────────────────────────────────────────────

def generate_subtitles(
    audio_path: Path,
    script: str,
    duration: float,
) -> List[SubtitleChunk]:
    """
    Generate karaoke-style subtitle chunks using local Whisper.

    Args:
        audio_path: Path to the .mp3 voiceover file.
        script:     Full script text (used for fallback only).
        duration:   Audio duration in seconds.

    Returns:
        List of SubtitleChunk objects ready for video_builder.
    """
    log.info(f"🔤 Generating subtitles for {duration:.1f}s audio...")

    try:
        word_timestamps = _transcribe_with_whisper(audio_path)
        if word_timestamps:
            chunks = _build_chunks(word_timestamps, config.SUBTITLE_WORDS_PER_LINE)
            log.info(f"✅ {len(chunks)} subtitle chunks generated via Whisper")
            return chunks
    except Exception as e:
        log.warning(f"Whisper transcription failed: {e}. Using fallback.")

    # Fallback
    word_timestamps = _distribute_timestamps(script, duration)
    chunks = _build_chunks(word_timestamps, config.SUBTITLE_WORDS_PER_LINE)
    log.info(f"✅ {len(chunks)} subtitle chunks generated via fallback")
    return chunks
