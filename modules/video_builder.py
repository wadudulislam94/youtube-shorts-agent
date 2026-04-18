"""
modules/video_builder.py (Free Edition — MoviePy 2.x compatible)
─────────────────────────────────────────────────────────────────────────────
Step 4b: Video Assembly using MoviePy 2.x + PIL + Pixabay (free).

Updated for MoviePy 2.x API:
  - .subclipped() instead of .subclip()
  - .resized() instead of .resize()
  - .cropped() instead of .crop()
  - .with_duration() instead of .set_duration()
  - .with_audio() instead of .set_audio()
  - .with_opacity() instead of .set_opacity()
  - .image_transform() for per-frame subtitle rendering
  - vfx.MultiplyColor / vfx.MultiplySpeed instead of colorx/speedx
"""

import math
import os
import random
import uuid
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger
from modules.subtitle_generator import SubtitleChunk

log = get_logger("VideoBuilder")

# ── Style Choices ──────────────────────────────────────────────────────────────
ACCENT_COLORS = [
    "#FFD700",  # Gold
    "#FF6B6B",  # Coral
    "#4ECDC4",  # Teal
    "#FF8B94",  # Salmon Pink
    "#FFE66D",  # Yellow
    "#A8E6CF",  # Mint
    "#C3A6FF",  # Lavender
    "#FFA07A",  # Light Salmon
]


# ── Pixabay Video Download ─────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _download_background_video(query: str) -> Path:
    """Search Pixabay for a free background video and download it."""
    if not config.PIXABAY_API_KEY:
        raise RuntimeError(
            "PIXABAY_API_KEY not set. Get free key at: https://pixabay.com/api/docs/"
        )

    log.info(f"🎬 Searching Pixabay for: '{query}'")

    def _search(q: str):
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key":        config.PIXABAY_API_KEY,
                "q":          q,
                "video_type": "film",
                "per_page":   15,
                "safesearch": "true",
                "lang":       "en",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("hits", [])

    hits = _search(query)
    if not hits:
        log.warning(f"No Pixabay results for '{query}'. Trying fallback.")
        hits = _search("nature landscape abstract")

    if not hits:
        raise RuntimeError("No Pixabay videos found.")

    video   = random.choice(hits[:8])
    videos  = video.get("videos", {})
    vid_url = None
    vid_info = None

    for quality in ("large", "medium", "small", "tiny"):
        if quality in videos and videos[quality].get("url"):
            vid_url  = videos[quality]["url"]
            vid_info = videos[quality]
            break

    if not vid_url:
        raise RuntimeError("No downloadable URL in Pixabay response.")

    log.info(f"⬇️  Downloading Pixabay video "
             f"({vid_info.get('width','?')}×{vid_info.get('height','?')})...")

    uid      = uuid.uuid4().hex[:8]
    out_path = config.OUTPUT_VIDEO / f"bg_{uid}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(vid_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    log.info(f"✅ Background saved: {out_path.name} ({size_mb:.1f}MB)")
    return out_path


# ── Font Loading ───────────────────────────────────────────────────────────────

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        config.ASSETS_FONTS / "Montserrat-ExtraBold.ttf",
        config.ASSETS_FONTS / "BebasNeue-Regular.ttf",
        config.ASSETS_FONTS / "Roboto-Bold.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/verdanab.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue

    log.warning("⚠️  No TTF font found — using PIL default.")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ── Subtitle Rendering ─────────────────────────────────────────────────────────

def _render_subtitle_on_frame(
    frame_array: np.ndarray,
    chunk: SubtitleChunk,
    accent_color: str,
) -> np.ndarray:
    """Overlay karaoke-style subtitles on a frame (numpy array → numpy array)."""
    img  = Image.fromarray(frame_array)
    draw = ImageDraw.Draw(img)
    W, H = img.size

    fs         = config.SUBTITLE_FONT_SIZE
    base_font  = _load_font(fs)
    big_font   = _load_font(int(fs * 1.12))

    word_texts = [w.word for w in chunk.words]
    y_center   = int(H * config.SUBTITLE_Y_POSITION)
    gap        = 18
    sw         = config.SUBTITLE_STROKE_WIDTH

    # Measure widths
    word_widths = []
    for i, wt in enumerate(word_texts):
        font = big_font if i == chunk.active_idx else base_font
        bbox = draw.textbbox((0, 0), wt, font=font)
        word_widths.append(bbox[2] - bbox[0])

    total_w = sum(word_widths) + gap * max(0, len(word_widths) - 1)
    x       = (W - total_w) // 2

    for i, (wt, ww) in enumerate(zip(word_texts, word_widths)):
        is_active = (i == chunk.active_idx)
        color     = accent_color if is_active else config.SUBTITLE_FONT_COLOR
        font      = big_font     if is_active else base_font

        # Stroke outline
        for dx, dy in [(-sw, 0), (sw, 0), (0, -sw), (0, sw),
                       (-sw, -sw), (sw, -sw), (-sw, sw), (sw, sw)]:
            draw.text((x + dx, y_center + dy), wt, font=font,
                      fill=config.SUBTITLE_STROKE_COLOR)

        draw.text((x, y_center), wt, font=font, fill=color)
        x += ww + gap

    return np.array(img)


def _find_chunk_at(chunks: List[SubtitleChunk], t: float) -> Optional[SubtitleChunk]:
    for chunk in chunks:
        if chunk.start <= t <= chunk.end:
            return chunk
    return None


# ── Dynamic Craft Pixabay Query ────────────────────────────────────────────────

# Map craft keywords → best Pixabay search term for authentic footage
_CRAFT_QUERY_MAP = [
    (["resin", "epoxy", "pour"],          "resin art pour satisfying"),
    (["pottery", "ceramic", "wheel", "clay", "glaze"], "pottery wheel clay throwing"),
    (["watercolor", "water color"],        "watercolor painting process"),
    (["acrylic", "canvas", "paint"],       "acrylic painting art process"),
    (["oil paint", "oil painting"],        "oil painting artist brush"),
    (["wood", "carv", "lathe", "chisel",
       "walnut", "maple", "lumber"],       "woodworking crafting process"),
    (["knit", "crochet", "yarn", "wool"], "knitting crochet handmade"),
    (["macrame", "weav", "fiber"],         "macrame weaving handmade"),
    (["jewelry", "bead", "wire"],          "jewelry making craft"),
    (["candle", "wax", "wick"],            "candle making craft"),
    (["soap", "lather", "swirl"],          "soap making craft satisfying"),
    (["sketch", "pencil", "draw"],         "drawing sketching pencil art"),
    (["origami", "paper fold", "paper"],   "origami paper folding"),
    (["sculpt", "figurine", "statue"],     "sculpting clay art"),
    (["glass", "stained", "mosaic"],       "glass art mosaic craft"),
    (["embroider", "stitch", "thread",
       "sew", "quilt", "fabric"],          "embroidery sewing handmade craft"),
    (["linocut", "block print", "stamp"],  "printmaking block print art"),
    (["leather"],                          "leather craft handmade"),
    (["satisfying", "oddly"],              "satisfying art craft timelapse"),
]

_ART_FALLBACKS = [
    "satisfying art craft painting",
    "art creation process timelapse",
    "handmade craft satisfying",
    "artist painting creating",
    "diy craft making process",
]


def _craft_video_query(topic: str, niche_cfg: dict) -> str:
    """
    Build a targeted Pixabay query from the craft topic.
    Falls back to niche config query if no keywords match.
    """
    topic_lower = topic.lower()

    for keywords, query in _CRAFT_QUERY_MAP:
        if any(kw in topic_lower for kw in keywords):
            log.info(f"🎯 Craft query matched: '{query}'")
            return query

    # Use niche default or a random art fallback
    default = niche_cfg.get("bg_video_query", "")
    if default and default != "satisfying art painting process":
        return default

    fallback = random.choice(_ART_FALLBACKS)
    log.info(f"🎨 Using art fallback query: '{fallback}'")
    return fallback



def build_video(
    audio_path: Path,
    subtitle_chunks: List[SubtitleChunk],
    audio_duration: float,
    topic: str,
) -> Path:
    """Render final YouTube Short MP4 — MoviePy 2.x compatible."""

    # MoviePy 2.x imports
    from moviepy import (
        VideoFileClip, AudioFileClip, CompositeVideoClip,
        ImageClip, concatenate_videoclips,
    )
    import moviepy.video.fx as vfx

    uid          = uuid.uuid4().hex[:8]
    output_path  = config.OUTPUT_FINAL / f"short_{uid}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    accent_color = random.choice(ACCENT_COLORS)
    niche_cfg    = config.get_niche()

    # ── Dynamic Pixabay query based on craft topic ──────────────────────────────
    bg_query = _craft_video_query(topic, niche_cfg)

    log.info(f"🎬 Building video | accent={accent_color} | uid={uid}")

    # 1. Download background
    bg_path = _download_background_video(bg_query)

    # 2. Load audio FIRST to get the real duration (the passed-in value may be estimated)
    audio_clip    = AudioFileClip(str(audio_path))
    real_duration = audio_clip.duration - 0.1   # 0.1s safety trim prevents end-of-file reads
    log.info(f"🔊 Audio duration: {audio_clip.duration:.2f}s → using {real_duration:.2f}s")

    # 3. Load background (no audio)
    bg_clip = VideoFileClip(str(bg_path), audio=False)

    # 4. Slight speed variation for uniqueness
    speed = random.uniform(0.95, 1.05)
    bg_clip = bg_clip.with_effects([vfx.MultiplySpeed(speed)])

    # 5. Loop if shorter than audio
    if bg_clip.duration < real_duration:
        loops   = math.ceil(real_duration / bg_clip.duration)
        bg_clip = concatenate_videoclips([bg_clip] * loops)

    bg_clip = bg_clip.subclipped(0, real_duration)

    # 6. Resize and crop to 1080×1920 (9:16)
    tw, th = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    cw, ch = bg_clip.size
    scale  = max(tw / cw, th / ch)
    new_w  = int(cw * scale)
    new_h  = int(ch * scale)
    bg_clip = bg_clip.resized((new_w, new_h))

    # Random crop offset for uniqueness
    max_x = max(0, new_w - tw)
    max_y = max(0, new_h - th)
    ox    = random.randint(0, max_x)
    oy    = random.randint(0, max_y)
    bg_clip = bg_clip.cropped(x1=ox, y1=oy, x2=ox + tw, y2=oy + th)

    # 7. Random color tint for uniqueness
    tint = random.uniform(0.85, 1.0)
    bg_clip = bg_clip.with_effects([vfx.MultiplyColor(tint)])

    # 8. Apply karaoke subtitles via transform()
    log.info("🔤 Applying karaoke subtitles...")

    def apply_subtitles(get_frame, t):
        frame = get_frame(t)
        chunk = _find_chunk_at(subtitle_chunks, t)
        if chunk is not None:
            frame = _render_subtitle_on_frame(frame, chunk, accent_color)
        return frame

    video_with_subs = bg_clip.transform(apply_subtitles)

    # 9. Gradient overlay (dark band behind subtitle zone)
    gradient_arr  = _make_gradient_overlay(tw, th)
    gradient_clip = (
        ImageClip(gradient_arr)
        .with_duration(real_duration)
        .with_opacity(0.55)
    )

    # 10. Composite
    final_clip = CompositeVideoClip([video_with_subs, gradient_clip])

    # 11. Attach audio — trim audio to match real_duration to be safe
    audio_clip = audio_clip.subclipped(0, real_duration)
    final_clip = final_clip.with_audio(audio_clip).with_duration(real_duration)

    # 11. Export
    log.info(f"🎞️  Exporting {tw}×{th} @ {config.VIDEO_FPS}fps → {output_path.name}")
    final_clip.write_videofile(
        str(output_path),
        fps=config.VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate=config.VIDEO_BITRATE,
        preset="fast",
        threads=4,
        logger=None,
    )

    # Cleanup
    for clip in [bg_clip, audio_clip, final_clip]:
        try:
            clip.close()
        except Exception:
            pass
    try:
        os.remove(bg_path)
    except Exception:
        pass

    size_mb = output_path.stat().st_size / (1024 * 1024)
    log.info(f"✅ Video complete: {output_path.name} ({size_mb:.1f}MB)")
    return output_path


def _make_gradient_overlay(width: int, height: int) -> np.ndarray:
    """Dark gradient band around subtitle zone for readability."""
    overlay = np.zeros((height, width, 3), dtype=np.uint8)
    sub_y   = int(height * config.SUBTITLE_Y_POSITION)
    band    = 200

    for y in range(max(0, sub_y - band), min(height, sub_y + band)):
        dist  = abs(y - sub_y)
        alpha = max(0.0, 1.0 - dist / band)
        val   = int(alpha * 35)
        overlay[y, :] = val

    return overlay
