"""
modules/video_builder.py — High-Retention Edition
─────────────────────────────────────────────────────────────────────────────
Produces scroll-stopping Shorts with:
  1. Multi-clip dynamic background  (4 Pixabay clips, Ken Burns zoom)
  2. Word-by-word ASS animated captions  (TikTok / Alex Hormozi style)
  3. Background music overlay  (from assets/music/ folder)
  4. Pure FFmpeg rendering  — no frame-by-frame Python loop
"""

import math
import os
import random
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger
from modules.subtitle_generator import SubtitleChunk

log = get_logger("VideoBuilder")

# ── ASS colour constants (AABBGGRR) ───────────────────────────────────────────
_ACCENT_PALETTE = [
    "&H0000FFFF",   # Yellow    ← most viral
    "&H0000FF7F",   # Green
    "&H00FF7FFF",   # Pink
    "&H007FFF00",   # Cyan-lime
]


# ══════════════════════════════════════════════════════════════════════════════
# 1. ASS SUBTITLE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _ass_ts(sec: float) -> str:
    """Seconds → ASS timestamp H:MM:SS.cc"""
    h  = int(sec // 3600)
    m  = int((sec % 3600) // 60)
    s  = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _generate_ass(chunks: List[SubtitleChunk], accent: str, out: Path, hook: str = "") -> Path:
    """
    Generate .ass subtitle file.
    Routes to anime style or standard style based on CONTENT_NICHE.
    """
    if config.CONTENT_NICHE == "anime":
        return _generate_ass_anime(chunks, out, hook=hook)
    return _generate_ass_standard(chunks, accent, out)


def _generate_ass_anime(chunks: List[SubtitleChunk], out: Path, hook: str = "") -> Path:
    """
    VIRAL-STYLE anime subtitles — reverse-engineered from 12M+ view Shorts.

    KEY DESIGN (based on @Anime_Dragons_Den viral style):
    ─────────────────────────────────────────────────────
    1. ONE WORD AT A TIME at screen center (y=60% from top)
       → No box, no karaoke, no phrases. Just the current word, BIG.
       → 120px bold white, 8px black outline, 5px shadow
    2. HOOK TITLE pinned at TOP throughout the whole video
       → Small semi-transparent box at top showing the story hook
       → Creates constant curiosity: viewer reads hook → wants to see resolution
    3. Word appears for its natural speech duration (word.start → word.end)
       → Guaranteed zero overlap: events are strictly sequential
    4. Subtle scale punch-in on each word (90% → 100% in 60ms)
       → Adds life without chaos
    """

    # ── Collect & sort all word timestamps ───────────────────────────────────
    seen: set = set()
    all_words = []
    for chunk in chunks:
        for w in chunk.words:
            key = (round(w.start, 3), w.word.strip().lower())
            if key not in seen:
                seen.add(key)
                all_words.append(w)
    all_words.sort(key=lambda w: w.start)

    total_end = (all_words[-1].end + 0.3) if all_words else 60.0

    # ── ASS header ────────────────────────────────────────────────────────────
    # Word style: large, centered, white, heavy outline, NO box
    #   Alignment=2  = bottom-center  → MarginV pushes it UP from the bottom
    #   MarginV=680  → word sits at (1920-680)=1240px from top = ~64% down
    #   (This puts the word below the art's focal point, readable but not covering faces)
    #
    # Hook style: small, top-center, semi-transparent box background
    #   Alignment=8  = top-center  → MarginV=90 = 90px from top
    header = """[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Roboto,118,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,5,2,60,60,680,1
Style: Hook,Roboto,38,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,2,1,8,100,100,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    # ── Event 1: Hook title pinned at top ─────────────────────────────────────
    if hook:
        # Clean the hook text for ASS (remove commas that break dialogue format)
        hook_clean = hook.strip().replace("\n", " ").replace(",", ".")[:120]
        hook_ts = _ass_ts(0.0)
        hook_te = _ass_ts(total_end)
        events.append(f"Dialogue: 0,{hook_ts},{hook_te},Hook,,0,0,0,,{hook_clean}")

    # ── Events: ONE word per event, sequential, no overlap ───────────────────
    if not all_words:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(header + "\n".join(events), encoding="utf-8")
        return out

    for w in all_words:
        txt = w.word.strip().upper()
        if not txt:
            continue
        ts = _ass_ts(w.start)
        te = _ass_ts(w.end + 0.05)   # tiny overlap so there's no flash of empty screen
        # Subtle punch-in: 90%→100% scale in 60ms
        pfx = r"{\fscx90\fscy90\t(0,60,\fscx100\fscy100)}"
        events.append(f"Dialogue: 0,{ts},{te},Word,,0,0,0,,{pfx}{txt}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n".join(events), encoding="utf-8")
    log.info(f"✅ Anime subtitles: {len(events)} phrase events ({len(all_words)} words) → {out.name}")
    return out




def _generate_ass_standard(chunks: List[SubtitleChunk], accent: str, out: Path) -> Path:
    """
    Original Hormozi-style word-by-word karaoke subtitles (non-anime niches).
    """
    font = getattr(config, "SUBTITLE_FONT_NAME", "Arial")

    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Active,{font},88,{accent},&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,2,0,1,6,3,2,60,60,230,1
Style: Normal,{font},88,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,2,0,1,5,2,2,60,60,230,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    for chunk in chunks:
        if not chunk.words:
            continue

        words = chunk.words

        for active_idx, active_word in enumerate(words):
            # Build full line with colour overrides per word
            parts = []
            for i, w in enumerate(words):
                txt = w.word.strip().upper()
                if not txt:
                    continue
                if i == active_idx:
                    parts.append(
                        r"{\c" + accent + r"\fscx112\fscy112}" + txt + r"{\r}"
                    )
                else:
                    parts.append(
                        r"{\c&H00FFFFFF&\fscx100\fscy100}" + txt + r"{\r}"
                    )

            if not parts:
                continue

            line = "  ".join(parts)
            ts   = _ass_ts(active_word.start)
            te   = _ass_ts(active_word.end + 0.04)

            if active_idx == 0:
                # Pop-in: scale from 0→112→100 over 150ms
                pfx = (
                    r"{\fscx0\fscy0"
                    r"\t(0,100,\fscx112\fscy112)"
                    r"\t(100,150,\fscx100\fscy100)}"
                )
                events.append(
                    f"Dialogue: 0,{ts},{te},Normal,,0,0,0,,{pfx}{line}"
                )
            else:
                events.append(
                    f"Dialogue: 0,{ts},{te},Normal,,0,0,0,,{line}"
                )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n".join(events), encoding="utf-8")
    log.info(f"📝 ASS subtitles: {len(events)} events → {out.name}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 2. MULTI-CLIP PIXABAY DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

_ART_FALLBACKS = [
    "satisfying art craft timelapse",
    "handmade craft making process",
    "art creation process",
    "painting artist studio",
]

_ANIME_FALLBACKS = [
    "fantasy landscape cinematic",
    "magic sword fight fantasy",
    "epic fantasy battle cinematic",
    "dragon fantasy landscape",
    "neon city cyberpunk night",
    "anime style fantasy art",
    "samurai sword fight cinematic",
    "magic spell fantasy cinematic",
]

_KEYWORD_QUERY_MAP = [
    (["resin", "epoxy pour", "resin art"],                   "resin art pour satisfying"),
    (["pottery", "clay wheel", "ceramic", "throwing"],        "pottery wheel clay throwing"),
    (["watercolor", "water colour"],                         "watercolor painting art"),
    (["acrylic", "canvas paint"],                            "acrylic painting canvas art"),
    (["oil paint"],                                          "oil painting artist brush"),
    (["wood", "carv", "chisel", "lathe", "walnut", "lumber"], "woodworking crafting process"),
    (["metal", "cast", "molten", "forge", "weld", "pour"],    "molten metal casting process"),
    (["sand cast"],                                          "sand casting metalwork foundry"),
    (["knit", "crochet", "yarn"],                            "knitting crochet handmade"),
    (["macrame", "weav", "fiber"],                           "macrame weaving fiber art"),
    (["jewelry", "ring", "necklace", "bead"],                "jewelry making handmade craft"),
    (["candle", "wax", "wick"],                              "candle making wax craft"),
    (["soap"],                                               "soap making craft satisfying"),
    (["glass", "stained glass", "mosaic"],                   "stained glass mosaic art"),
    (["sketch", "pencil", "draw", "illustrat"],              "drawing sketching pencil art"),
    (["origami", "paper fold"],                              "origami paper folding art"),
    (["sculpt", "figurine", "statue"],                       "clay sculpture sculpting art"),
    (["leather"],                                            "leather craft handmade"),
    (["embroid", "stitch", "sewing", "quilt"],               "embroidery sewing handmade"),
    (["print", "stamp", "linocut", "block print"],           "printmaking block print art"),
    (["calligraph", "brush letter"],                         "calligraphy brush art"),
    (["glaze", "kiln", "firing"],                            "ceramic glazing kiln pottery"),
    (["epoxy table", "river table", "geode"],                "epoxy resin river table"),
    (["mosaic", "tile art"],                                 "mosaic tile art craft"),
    (["silk", "fabric dye", "tie dye"],                      "fabric dyeing tie dye art"),
    (["knife", "blade", "blacksmith"],                       "blacksmith knife making forge"),
    (["satisfying", "oddly", "mesmeriz", "timelapse"],       "satisfying craft timelapse"),
    (["paint", "brush", "color"],                            "painting art brush process"),
    # Anime / fantasy keywords
    (["speedrun", "glitch", "rpg", "gamer", "game"],         "fantasy rpg game magic cinematic"),
    (["demon lord", "demon king", "final boss"],             "dark fantasy castle cinematic"),
    (["isekai", "reincarnate", "reincarnation"],             "fantasy landscape magic portal"),
    (["samurai", "sword", "katana", "warrior"],              "samurai sword fight cinematic"),
    (["magic", "spell", "mage", "wizard", "sorcerer"],       "magic spell fantasy effect"),
    (["dragon", "beast", "monster"],                         "dragon fantasy cinematic"),
    (["hero", "protagonist", "chosen one"],                  "epic fantasy hero cinematic"),
    (["battle", "fight", "clash", "war"],                    "epic fantasy battle cinematic"),
    (["kingdom", "castle", "dungeon", "quest"],              "medieval castle fantasy cinematic"),
    (["power", "level", "overpowered", "strongest"],         "neon energy power cinematic"),
    (["cyberpunk", "neon", "futuristic city"],               "cyberpunk neon city night"),
    (["streamer", "live", "broadcast"],                      "neon technology screen broadcast"),
    (["chess", "strategy", "mastermind"],                    "chess board strategy cinematic"),
]


def _topic_queries(topic: str, script: str = "") -> List[str]:
    """Extract Pixabay search queries by scanning topic + script for visual keywords."""
    # Scan both the topic title AND the first 400 chars of the script
    combined = (topic + " " + script[:400]).lower()

    matched = []
    for keywords, query in _KEYWORD_QUERY_MAP:
        if any(kw in combined for kw in keywords):
            if query not in matched:
                matched.append(query)
            if len(matched) >= 3:
                break

    if not matched:
        # Use niche-appropriate fallback queries
        import config as _cfg
        if _cfg.CONTENT_NICHE == "anime":
            matched = [random.choice(_ANIME_FALLBACKS)]
        else:
            matched = [random.choice(_ART_FALLBACKS)]

    # Add a variety fallback as a 4th option
    fallback_pool = _ANIME_FALLBACKS if (len(matched) > 0 and matched[0] in _ANIME_FALLBACKS) else _ART_FALLBACKS
    matched.append(random.choice(fallback_pool))
    log.info(f"🎯 Pixabay queries from script: {matched[:3]}")
    return matched[:4]


def _pixabay_hits(query: str) -> list:
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": config.PIXABAY_API_KEY,
                "q": query, "video_type": "film",
                "per_page": 12, "safesearch": "true", "lang": "en",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("hits", [])
    except Exception as e:
        log.warning(f"Pixabay search '{query}': {e}")
        return []


def _dl_clip(hit: dict, idx: int) -> Optional[Path]:
    vids = hit.get("videos", {})
    url  = None
    for q in ("large", "medium", "small", "tiny"):
        if q in vids and vids[q].get("url"):
            url = vids[q]["url"]
            break
    if not url:
        return None

    uid  = uuid.uuid4().hex[:6]
    dest = config.OUTPUT_VIDEO / f"clip_{idx}_{uid}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for ch in r.iter_content(65536):
                    if ch:
                        f.write(ch)
        return dest
    except Exception as e:
        log.warning(f"Clip {idx} download failed: {e}")
        return None


def _image_to_clip(img_path: Path, idx: int, dur: float = 20.0) -> Optional[Path]:
    """
    Convert a still image (JPEG/PNG) to a short MP4 clip.
    Used to turn Pollinations anime panels into video clips.
    """
    uid = uuid.uuid4().hex[:6]
    dst = config.OUTPUT_VIDEO / f"img_clip_{idx}_{uid}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    ok = _run([
        "-loop", "1",
        "-i", str(img_path),
        "-t", str(dur + 1.0),
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-r", "30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-an", str(dst),
    ], "img_to_clip")
    return dst if ok and dst.exists() else None


def _download_clips(topic: str, n: int = 4, script: str = "") -> List[Path]:
    """
    For ANIME niche: generate AI anime panels via Pollinations, then convert to clips.
    For all other niches: download stock footage from Pixabay.
    """
    # ── Anime mode: AI-generated art panels ──────────────────────────────────
    if config.CONTENT_NICHE == "anime":
        try:
            from modules.anime_image_generator import generate_anime_panels
            log.info("🎨 Anime mode: generating AI art panels instead of Pixabay clips")
            images = generate_anime_panels(topic, script)
            clips = []
            for i, img in enumerate(images):
                clip = _image_to_clip(img, i, dur=20.0)
                if clip:
                    clips.append(clip)
                    log.info(f"  🎞 Panel {i+1} converted to video clip")
                try:
                    img.unlink()
                except Exception:
                    pass
            if clips:
                return clips
            log.warning("Anime panel conversion failed — falling back to Pixabay")
        except Exception as e:
            log.warning(f"Anime image generation failed: {e} — falling back to Pixabay")

    # ── Standard mode: Pixabay stock footage ─────────────────────────────────
    queries  = _topic_queries(topic, script)
    clips    = []
    seen_ids: set = set()

    for query in queries * 2:
        if len(clips) >= n:
            break
        for hit in _pixabay_hits(query):
            if hit.get("id") in seen_ids:
                continue
            seen_ids.add(hit.get("id"))
            p = _dl_clip(hit, len(clips))
            if p:
                clips.append(p)
                log.info(f"  📥 Clip {len(clips)}/{n}: {p.name}")
                break

    if not clips:
        log.warning("No clips downloaded — trying generic fallback")
        for hit in _pixabay_hits("satisfying art process"):
            p = _dl_clip(hit, 0)
            if p:
                clips.append(p)
                break

    return clips



# ══════════════════════════════════════════════════════════════════════════════
# 3. FFMPEG HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _run(args: List[str], tag: str = "") -> bool:
    """Run FFmpeg. Returns True on success."""
    cmd = ["ffmpeg", "-y"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        if r.returncode != 0:
            err = r.stderr.decode("utf-8", errors="replace")[-600:]
            log.warning(f"FFmpeg [{tag}] rc={r.returncode}\n{err}")
            return False
        return True
    except Exception as e:
        log.error(f"FFmpeg [{tag}] exception: {e}")
        return False


def _normalize_clip(src: Path, dst: Path, dur: float) -> bool:
    """Scale → crop → Ken Burns zoom → fixed 1080×1920 @ 30fps."""
    W, H = 1080, 1920
    z0   = random.uniform(1.00, 1.04)
    z1   = random.uniform(1.05, 1.10)
    fps  = 30
    # Ken Burns: slowly zoom in across the clip duration
    n_frames = int(dur * fps)
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='if(lte(on,1),{z0:.3f},min(zoom+{(z1-z0)/n_frames:.5f},{z1:.3f}))':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps},"
        f"setpts=PTS-STARTPTS"
    )
    return _run([
        "-i", str(src),
        "-t", str(dur + 0.5),
        "-vf", vf,
        "-r", str(fps),
        "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        str(dst),
    ], "normalize")


def _assemble_background(clips: List[Path], total_dur: float) -> Path:
    """
    Concatenate clips with FFmpeg xfade transitions → single 1080×1920 video.
    """
    uid = uuid.uuid4().hex[:8]
    out = config.OUTPUT_VIDEO / f"bg_{uid}.mp4"

    n        = len(clips)
    fade_dur = 0.35
    fps      = 30
    # KEY FIX: xfade reduces total duration by (n-1)*fade_dur
    # So each clip must be longer to compensate:
    #   total_out = n * clip_dur - (n-1) * fade_dur  → solve for clip_dur
    n_fades  = max(0, n - 1)
    clip_dur = (total_dur + n_fades * fade_dur) / n
    log.info(f"🎞  Clip dur: {clip_dur:.2f}s × {n} clips - {n_fades} fades = {clip_dur*n - n_fades*fade_dur:.2f}s (target {total_dur:.2f}s)")

    # Normalize each clip
    normed = []
    for i, clip in enumerate(clips):
        dst = config.OUTPUT_VIDEO / f"n{i}_{uid}.mp4"
        if _normalize_clip(clip, dst, clip_dur + fade_dur + 0.5):
            normed.append(dst)
        else:
            log.warning(f"Normalise failed for clip {i}")

    if not normed:
        raise RuntimeError("All clip normalisations failed")

    if len(normed) == 1:
        # Single clip — just loop it
        _run([
            "-stream_loop", "-1",
            "-i", str(normed[0]),
            "-t", str(total_dur),
            "-c", "copy", str(out),
        ], "loop_single")
        _cleanup(normed)
        return out

    # Build xfade filter chain: [0][1]xfade=offset=T[x1]; [x1][2]xfade=offset=T2[x2]...
    inputs = []
    for n_path in normed:
        inputs += ["-i", str(n_path)]

    n        = len(normed)
    fc_parts = []
    last_tag = "[0:v]"

    for i in range(1, n):
        offset   = clip_dur * i - fade_dur * i
        out_tag  = f"[xf{i}]" if i < n - 1 else "[outv]"
        fc_parts.append(
            f"{last_tag}[{i}:v]xfade=transition=fade:"
            f"duration={fade_dur:.2f}:offset={offset:.2f}{out_tag}"
        )
        last_tag = out_tag

    fc = ";".join(fc_parts)

    success = _run(
        inputs
        + ["-filter_complex", fc,
           "-map", "[outv]",
           "-t", str(total_dur + 0.5),   # slight over-render, trimmed later
           "-r", str(fps),
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-an", str(out)],
        "xfade_assemble",
    )

    _cleanup(normed)

    if not success or not out.exists():
        # fallback: just use the first normalised clip looped
        log.warning("xfade failed — falling back to single looped clip")
        n0 = config.OUTPUT_VIDEO / f"n0_{uid}_fb.mp4"
        _normalize_clip(clips[0], n0, total_dur)
        _run(["-stream_loop", "-1", "-i", str(n0),
              "-t", str(total_dur), "-c", "copy", str(out)], "fallback_loop")
        try:
            os.remove(n0)
        except Exception:
            pass

    return out


# ══════════════════════════════════════════════════════════════════════════════
# 4. BACKGROUND MUSIC
# ══════════════════════════════════════════════════════════════════════════════

def _find_music() -> Optional[Path]:
    """Return a random music file from assets/music/ if any exist."""
    music_dir = config.BASE_DIR / "assets" / "music"
    if not music_dir.exists():
        return None
    tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.m4a"))
    return random.choice(tracks) if tracks else None


# ══════════════════════════════════════════════════════════════════════════════
# 5. FINAL RENDER
# ══════════════════════════════════════════════════════════════════════════════

def _final_render(
    bg: Path,
    ass: Path,
    audio: Path,
    music: Optional[Path],
    duration: float,
    out: Path,
) -> bool:
    """
    2-step FFmpeg render:
      Step 1 — Burn ASS subtitles into video (no audio)
      Step 2 — Mux voiceover + optional background music
    Avoids the -vf / -filter_complex conflict.
    """
    uid = uuid.uuid4().hex[:6]

    # Escape ASS path for FFmpeg subtitles filter
    ass_str = str(ass).replace("\\", "/")
    if ":" in ass_str:
        # Windows drive letter — escape the colon
        parts = ass_str.split(":", 1)
        ass_str = parts[0] + "\\:" + parts[1]

    # ── Step 1: Burn subtitles ──────────────────────────────────────────────
    # -stream_loop -1 ensures bg loops if slightly short (prevents freeze)
    subbed = out.parent / f"subbed_{uid}.mp4"
    ok = _run([
        "-stream_loop", "-1",
        "-i", str(bg),
        "-vf", f"ass='{ass_str}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-b:v", "4M",
        "-an",
        "-t", str(duration),          # output duration limit
        str(subbed),
    ], "burn_subs")

    if not ok or not subbed.exists():
        log.warning("Subtitle burn failed — trying without subtitles")
        # Fallback: just copy bg as subbed
        _run(["-i", str(bg), "-t", str(duration), "-c", "copy", str(subbed)], "fallback_copy")

    # ── Step 2: Mux voiceover + optional music ──────────────────────────────
    if music and music.exists() and music.stat().st_size > 10000:
        # -stream_loop -1 loops the music infinitely; -t cuts it at duration
        mux_cmd = [
            "-i",           str(subbed),          # 0: video (no audio)
            "-i",           str(audio),            # 1: voiceover
            "-stream_loop", "-1",
            "-i",           str(music),            # 2: background music (looped)
            "-t",           str(duration),
            "-filter_complex",
            "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map",  "0:v",
            "-map",  "[aout]",
            "-c:v",  "copy",
            "-c:a",  "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]
    else:
        # No music — simple mux
        mux_cmd = [
            "-i",  str(subbed),
            "-i",  str(audio),
            "-t",  str(duration),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]

    success = _run(mux_cmd, "mux_audio")
    _cleanup([subbed])
    return success


def _cleanup(paths):
    for p in paths:
        try:
            if p and Path(p).exists():
                os.remove(p)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# 6. PUBLIC INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

def build_video(
    audio_path: Path,
    subtitle_chunks: List[SubtitleChunk],
    audio_duration: float,
    topic: str,
    script: str = "",
    hook: str = "",
) -> Path:
    """
    Render a high-retention YouTube Short.

    Pipeline:
      1. Download 4 Pixabay clips matched to topic + script keywords
      2. Assemble with xfade crossfades + Ken Burns zoom
      3. Generate ASS word-by-word animated subtitles
      4. Final FFmpeg render: subtitles + audio + optional music
    """
    uid        = uuid.uuid4().hex[:8]
    out_path   = config.OUTPUT_FINAL / f"short_{uid}.mp4"
    ass_path   = config.OUTPUT_FINAL / f"subs_{uid}.ass"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    accent = random.choice(_ACCENT_PALETTE)
    log.info(f"🎬 High-Retention Builder | accent={accent} | uid={uid}")
    log.info(f"   Script keywords: {script[:80]}..." if script else "   No script provided")

    # Real audio duration (authoritative)
    duration = float(audio_duration)

    # ── Step A: Download multi-clip background ─────────────────────────────
    log.info("📥 Downloading Pixabay clips matched to script...")
    raw_clips = _download_clips(str(topic), n=4, script=script)

    # ── Step B: Assemble & normalise background ────────────────────────────
    log.info("🎞  Assembling multi-clip background...")
    bg_path = _assemble_background(raw_clips, duration)

    # ── Step C: Generate ASS subtitles ─────────────────────────────────────
    log.info("🔤 Generating ASS animated subtitles...")
    _generate_ass(subtitle_chunks, accent, ass_path, hook=hook)

    # ── Step D: Find background music (optional) ───────────────────────────
    music = _find_music()
    if music:
        log.info(f"🎵 Background music: {music.name}")
    else:
        log.info("🔇 No music tracks in assets/music/ — skipping BGM")

    # ── Step E: Final render ───────────────────────────────────────────────
    log.info(f"🎬 Final FFmpeg render → {out_path.name}")
    success = _final_render(bg_path, ass_path, audio_path, music, duration, out_path)

    # Cleanup temp files
    _cleanup(raw_clips)
    _cleanup([bg_path])
    try:
        ass_path.unlink()
    except Exception:
        pass

    if not success or not out_path.exists():
        raise RuntimeError("Final FFmpeg render failed — check logs above")

    size_mb = out_path.stat().st_size / (1024 * 1024)
    log.info(f"✅ Video complete: {out_path.name} ({size_mb:.1f}MB)")
    return out_path
