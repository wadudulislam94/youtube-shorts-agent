"""
modules/uploader.py
─────────────────────────────────────────────────────────────────────────────
Step 5b: YouTube Upload using YouTube Data API v3.

Handles OAuth 2.0 authentication (first-time browser login, then token refresh)
and uploads the final .mp4 as a YouTube Short with full metadata.

First run: Opens browser for Google OAuth consent.
Subsequent runs: Uses saved token (auto-refreshed).
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from logger import get_logger
from modules.seo_generator import SEOResult

log = get_logger("Uploader")

YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION  = "v3"


# ── OAuth Authentication ───────────────────────────────────────────────────────

def _get_authenticated_service():
    """
    Build an authenticated YouTube service object.
    
    First run: Opens browser for Google OAuth consent screen.
    Subsequent runs: Loads saved token and refreshes if expired.
    
    Returns:
        Authenticated YouTube API service.
    """
    creds = None
    token_path = Path(config.YOUTUBE_TOKEN_FILE)
    secrets_path = Path(config.YOUTUBE_CLIENT_SECRETS)

    if not secrets_path.exists():
        raise FileNotFoundError(
            f"YouTube client_secrets.json not found at: {secrets_path}\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials."
        )

    # Load existing token
    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("🔄 Refreshing YouTube OAuth token...")
            creds.refresh(Request())
        else:
            log.info("🌐 Opening browser for YouTube OAuth consent...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(secrets_path),
                scopes=config.YOUTUBE_SCOPES,
            )
            creds = flow.run_local_server(
                port=8085,
                open_browser=False,
                authorization_prompt_message="AUTH_URL: {url}",
            )

        # Save token for next run
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        log.info(f"💾 OAuth token saved to {token_path}")

    return build(
        YOUTUBE_API_SERVICE,
        YOUTUBE_API_VERSION,
        credentials=creds,
    )


# ── Upload ─────────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True,
)
def upload_to_youtube(video_path: Path, seo: SEOResult) -> Optional[str]:
    """
    Upload the rendered Short to YouTube with full metadata.
    
    Args:
        video_path: Path to the final .mp4 file.
        seo:        SEOResult with title, description, tags, category_id.
    
    Returns:
        YouTube video ID string if successful, None on failure.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    log.info(f"📤 Uploading to YouTube: {video_path.name}")
    log.info(f"   Title: {seo.title}")

    service = _get_authenticated_service()

    # Build request body
    body = {
        "snippet": {
            "title": seo.title,
            "description": seo.description,
            "tags": seo.tags,
            "categoryId": seo.category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            # NOTE: Monetization is channel-level; you enable it in YouTube Studio
            # after meeting Partner Program requirements (1K subs + 10M Shorts views)
        },
    }

    # MediaFileUpload with resumable=True is critical for large files
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
    )

    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    # Execute with progress logging
    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info(f"   Upload progress: {pct}%")
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                log.warning(f"HTTP {e.resp.status} — retrying upload chunk...")
                raise  # Let tenacity handle retry
            else:
                log.error(f"Non-retryable upload error: {e}")
                raise

    video_id = response.get("id")
    video_url = f"https://www.youtube.com/shorts/{video_id}"

    log.info(f"🎉 Upload COMPLETE!")
    log.info(f"   Video ID:  {video_id}")
    log.info(f"   Short URL: {video_url}")

    return video_id


def set_thumbnail(service, video_id: str, thumbnail_path: Path) -> bool:
    """
    Optional: Upload a custom thumbnail for the video.
    Requires channel to be verified.
    """
    if not thumbnail_path.exists():
        return False
    try:
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
        ).execute()
        log.info(f"🖼️  Thumbnail uploaded for video {video_id}")
        return True
    except HttpError as e:
        log.warning(f"Thumbnail upload failed (requires verified channel): {e}")
        return False
