"""
modules/cross_poster.py — TikTok + Instagram Auto-Poster
─────────────────────────────────────────────────────────────────────────────
Posts each Short to TikTok and Instagram Reels automatically after YouTube.

Setup (one time):
  1. Run: python setup_social.py
  2. Add the tokens to GitHub Secrets (see README for names)
  3. That's it — every new Short posts to 3 platforms automatically.

Platforms:
  ✅ TikTok        — Content Posting API v2 (direct chunked upload)
  ✅ Instagram      — Meta Graph API v18.0 (video via temp CDN)
"""

import math
import os
import time
from pathlib import Path
from typing import Optional

import requests

import config
from logger import get_logger

log = get_logger("CrossPoster")

# ── Credentials (set via .env / GitHub Secrets) ───────────────────────────────
TIKTOK_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
IG_USER_ID   = os.getenv("INSTAGRAM_USER_ID", "")
IG_TOKEN     = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")


# ══════════════════════════════════════════════════════════════════════════════
# 1.  TIKTOK
# ══════════════════════════════════════════════════════════════════════════════

def _tiktok_post(video_path: Path, title: str) -> Optional[str]:
    """Upload and publish a video to TikTok via Content Posting API v2."""
    if not TIKTOK_TOKEN:
        log.warning("TIKTOK_ACCESS_TOKEN not set — skipping TikTok")
        return None

    video_size  = video_path.stat().st_size
    chunk_size  = 10 * 1024 * 1024          # 10 MB per chunk
    total_chunks = math.ceil(video_size / chunk_size)

    headers = {
        "Authorization": f"Bearer {TIKTOK_TOKEN}",
        "Content-Type":  "application/json; charset=UTF-8",
    }

    # ── Step 1: Init upload ───────────────────────────────────────────────────
    init_resp = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title":                    title[:150],
                "privacy_level":            "PUBLIC_TO_EVERYONE",
                "disable_duet":             False,
                "disable_comment":          False,
                "disable_stitch":           False,
                "video_cover_timestamp_ms": 2000,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        video_size,
                "chunk_size":        chunk_size,
                "total_chunk_count": total_chunks,
            },
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    init_data = init_resp.json()

    if init_data.get("error", {}).get("code") != "ok":
        raise ValueError(f"TikTok init error: {init_data}")

    publish_id = init_data["data"]["publish_id"]
    upload_url = init_data["data"]["upload_url"]
    log.info(f"  TikTok upload started | publish_id={publish_id}")

    # ── Step 2: Upload chunks ─────────────────────────────────────────────────
    with open(video_path, "rb") as fh:
        for idx in range(total_chunks):
            chunk     = fh.read(chunk_size)
            start     = idx * chunk_size
            end       = start + len(chunk) - 1
            requests.put(
                upload_url,
                headers={
                    "Content-Range":  f"bytes {start}-{end}/{video_size}",
                    "Content-Type":   "video/mp4",
                    "Content-Length": str(len(chunk)),
                },
                data=chunk,
                timeout=120,
            ).raise_for_status()
            log.info(f"  TikTok chunk {idx+1}/{total_chunks} ✓")

    # ── Step 3: Poll publish status ───────────────────────────────────────────
    for _ in range(12):
        time.sleep(6)
        st = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
            timeout=30,
        ).json()
        status = st.get("data", {}).get("status", "")
        log.info(f"  TikTok status: {status}")
        if status == "PUBLISH_COMPLETE":
            log.info(f"✅ TikTok posted | publish_id={publish_id}")
            return publish_id
        if status in ("FAILED", "REJECTED"):
            raise ValueError(f"TikTok publish failed: {st}")

    log.warning("TikTok status timed out — video may still be processing")
    return publish_id


# ══════════════════════════════════════════════════════════════════════════════
# 2.  INSTAGRAM REELS
# ══════════════════════════════════════════════════════════════════════════════

def _upload_to_cdn(video_path: Path) -> str:
    """
    Upload video to catbox.moe (free, no account, 72-hour retention).
    Returns a publicly accessible HTTPS URL that Instagram can fetch.
    """
    log.info("  Uploading to temp CDN for Instagram...")
    with open(video_path, "rb") as fh:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": ("short.mp4", fh, "video/mp4")},
            timeout=180,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise ValueError(f"CDN upload failed: {url}")
    log.info(f"  CDN URL: {url}")
    return url


def _instagram_post(video_path: Path, caption: str) -> Optional[str]:
    """Publish a Reel to Instagram via Meta Graph API v18.0."""
    if not IG_USER_ID or not IG_TOKEN:
        log.warning("INSTAGRAM_USER_ID / INSTAGRAM_ACCESS_TOKEN not set — skipping Instagram")
        return None

    base = "https://graph.instagram.com/v18.0"

    # ── Step 1: Get public video URL ──────────────────────────────────────────
    video_url = _upload_to_cdn(video_path)

    # ── Step 2: Create media container ───────────────────────────────────────
    log.info("  Creating Instagram Reels container...")
    cr = requests.post(
        f"{base}/{IG_USER_ID}/media",
        params={
            "media_type":    "REELS",
            "video_url":     video_url,
            "caption":       caption[:2200],
            "share_to_feed": "true",
            "access_token":  IG_TOKEN,
        },
        timeout=60,
    ).json()

    if "error" in cr:
        raise ValueError(f"Instagram container error: {cr['error']}")

    container_id = cr["id"]
    log.info(f"  Container: {container_id}")

    # ── Step 3: Wait for video processing ────────────────────────────────────
    for _ in range(20):
        time.sleep(8)
        st = requests.get(
            f"{base}/{container_id}",
            params={"fields": "status_code", "access_token": IG_TOKEN},
            timeout=30,
        ).json()
        code = st.get("status_code", "")
        log.info(f"  Instagram processing: {code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise ValueError(f"Instagram video processing failed: {st}")

    # ── Step 4: Publish ───────────────────────────────────────────────────────
    log.info("  Publishing Reel...")
    pub = requests.post(
        f"{base}/{IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": IG_TOKEN},
        timeout=30,
    ).json()

    if "error" in pub:
        raise ValueError(f"Instagram publish error: {pub['error']}")

    media_id = pub["id"]
    log.info(f"✅ Instagram Reel posted | media_id={media_id}")
    return media_id


# ══════════════════════════════════════════════════════════════════════════════
# 3.  PUBLIC INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

def cross_post(video_path: Path, title: str, description: str) -> dict:
    """
    Post the Short to all configured social platforms.

    Never raises — failures are logged but the main pipeline continues.

    Returns:
        {"tiktok": "publish_id|skipped|failed",
         "instagram": "media_id|skipped|failed"}
    """
    results = {}
    log.info("\n📲 Cross-posting to social platforms...")

    for name, fn, args in [
        ("tiktok",    _tiktok_post,    (video_path, title)),
        ("instagram", _instagram_post, (video_path, f"{title}\n\n{description}")),
    ]:
        try:
            result         = fn(*args)
            results[name]  = result or "skipped"
        except Exception as exc:
            results[name] = "failed"
            log.error(f"❌ {name.capitalize()} failed: {exc}")

    success = [k for k, v in results.items() if v not in ("skipped", "failed")]
    log.info(f"📲 Cross-post summary: {results}")
    if success:
        log.info(f"✅ Posted to: {', '.join(success)}")
    return results
