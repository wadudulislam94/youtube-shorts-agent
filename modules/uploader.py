"""
modules/uploader.py
─────────────────────────────────────────────────────────────────────────────
Step 5b: YouTube Upload using YouTube Data API v3.

Token stored as JSON (not pickle) so it works on any OS including
GitHub Actions Linux runners.
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
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


# ── Token Save / Load (JSON format — works on any OS) ─────────────────────────

def _save_token(creds: Credentials, token_path: Path):
    """Save credentials as JSON (cross-platform, GitHub Actions compatible)."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else list(config.YOUTUBE_SCOPES),
        "expiry":        creds.expiry.isoformat() if creds.expiry else None,
    }
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log.info(f"💾 OAuth token saved to {token_path}")


def _load_token(token_path: Path) -> Optional[Credentials]:
    """Load credentials from JSON or legacy pickle file."""
    if not token_path.exists():
        return None

    # Try JSON format first
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        expiry = None
        if data.get("expiry"):
            try:
                expiry = datetime.fromisoformat(data["expiry"])
                # google-auth uses naive UTC datetimes — strip tzinfo if present
                if expiry.tzinfo is not None:
                    expiry = expiry.replace(tzinfo=None)
            except Exception:
                pass

        return Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", config.YOUTUBE_SCOPES),
            expiry=expiry,
        )
    except (json.JSONDecodeError, KeyError):
        pass

    # Fall back to legacy pickle format (converts & re-saves as JSON)
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        log.info("🔄 Migrating token from pickle → JSON format...")
        _save_token(creds, token_path)
        return creds
    except Exception:
        pass

    return None


# ── OAuth Authentication ───────────────────────────────────────────────────────

def _get_authenticated_service():
    """
    Build an authenticated YouTube service object.
    Loads saved JSON token and refreshes if expired.
    """
    creds = None
    token_path   = Path(config.YOUTUBE_TOKEN_FILE)
    secrets_path = Path(config.YOUTUBE_CLIENT_SECRETS)

    if not secrets_path.exists():
        raise FileNotFoundError(
            f"YouTube client_secrets.json not found at: {secrets_path}\n"
            "See README for setup instructions."
        )

    creds = _load_token(token_path)

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
                open_browser=True,
                authorization_prompt_message="",
                success_message="Authorization complete. You may close this window.",
            )

        _save_token(creds, token_path)

    return build(YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION, credentials=creds)


# ── Upload ─────────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True,
)
def upload_to_youtube(video_path: Path, seo: SEOResult) -> Optional[str]:
    """Upload the rendered Short to YouTube with full metadata."""
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    log.info(f"📤 Uploading to YouTube: {video_path.name}")
    log.info(f"   Title: {seo.title}")

    service = _get_authenticated_service()

    body = {
        "snippet": {
            "title":                seo.title,
            "description":          seo.description,
            "tags":                 seo.tags,
            "categoryId":           seo.category_id,
            "defaultLanguage":      "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus":            "public",
            "selfDeclaredMadeForKids":  False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,
    )

    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

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
                raise
            else:
                log.error(f"Non-retryable upload error: {e}")
                raise

    video_id  = response.get("id")
    video_url = f"https://www.youtube.com/shorts/{video_id}"

    log.info(f"🎉 Upload COMPLETE!")
    log.info(f"   Video ID:  {video_id}")
    log.info(f"   Short URL: {video_url}")

    return video_id
