"""
main.py — YouTube Shorts Agent Orchestrator
─────────────────────────────────────────────────────────────────────────────
This is the entry point. It:
  1. Runs the full pipeline (Trends → Script → TTS → Subtitles → Video → Upload)
  2. Schedules itself to run every N hours (configurable in .env)
  3. Handles all errors gracefully so crashes don't stop the scheduler

Usage:
  python main.py              # Run once immediately, then start scheduler
  python main.py --once       # Run once and exit (good for testing)
  python main.py --schedule   # Start scheduler only (skip initial run)
"""

import sys
import time
import argparse
import traceback
from datetime import datetime
from pathlib import Path

import schedule

import config
from logger import get_logger
from modules.trend_finder import discover_topic
from modules.script_generator import generate_script
from modules.tts_generator import generate_voiceover, get_audio_duration
from modules.subtitle_generator import generate_subtitles
from modules.video_builder import build_video
from modules.seo_generator import generate_seo
from modules.uploader import upload_to_youtube
from modules.cross_poster import cross_post

log = get_logger("Main")


def run_pipeline() -> bool:
    """
    Execute the full YouTube Shorts production pipeline.
    
    Returns:
        True if a Short was successfully produced and uploaded, False otherwise.
    """
    start_time = datetime.now()
    log.info("=" * 65)
    log.info(f"🚀 YouTube Shorts Agent — Pipeline START")
    log.info(f"   Niche: {config.CONTENT_NICHE}  |  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 65)

    video_path = None
    audio_path = None

    try:
        # ── Step 1: Trend Discovery ────────────────────────────────────────────
        log.info("\n📌 STEP 1/5 — Trend Discovery")
        topic_ref = discover_topic()          # ViralReference object
        topic     = str(topic_ref)             # plain string for logging/SEO/video
        log.info(f"   Topic: {topic}")

        # ── Step 2: Script Generation ──────────────────────────────────────────
        log.info("\n✍️  STEP 2/5 — Script Generation")
        script_result = generate_script(topic_ref)  # pass full ref for transcript
        log.info(f"   Script: {script_result.word_count} words | "
                 f"~{script_result.estimated_duration_sec:.0f}s")

        # ── Step 3: TTS Voiceover ──────────────────────────────────────────────
        log.info("\n🎙️  STEP 3/5 — TTS Voiceover")
        audio_path = generate_voiceover(script_result.full_script)
        audio_duration = get_audio_duration(audio_path)
        log.info(f"   Audio: {audio_path.name} | {audio_duration:.1f}s")

        # ── Step 4: Subtitles + Video Building ────────────────────────────────
        log.info("\n🎬 STEP 4/5 — Video Production")
        subtitle_chunks = generate_subtitles(
            audio_path=audio_path,
            script=script_result.full_script,
            duration=audio_duration,
        )
        log.info(f"   Subtitles: {len(subtitle_chunks)} chunks generated")

        video_path = build_video(
            audio_path=audio_path,
            subtitle_chunks=subtitle_chunks,
            audio_duration=audio_duration,
            topic=topic,
            script=script_result.full_script,
        )
        log.info(f"   Video: {video_path.name}")

        # ── Step 5: SEO + Upload ───────────────────────────────────────────────
        log.info("\n📤 STEP 5/5 — SEO + YouTube Upload")
        seo = generate_seo(topic=topic, script=script_result.full_script)

        video_id  = upload_to_youtube(video_path=video_path, seo=seo)
        short_url = f"https://www.youtube.com/shorts/{video_id}"

        # ── Step 6: Cross-post to TikTok + Instagram ──────────────────────────
        log.info("\n📲 STEP 6 — Cross-posting to TikTok + Instagram")
        social = cross_post(
            video_path=video_path,
            title=seo.title,
            description=seo.description,
        )

        # ── Summary ───────────────────────────────────────────────────────────
        elapsed = (datetime.now() - start_time).total_seconds()
        log.info("\n" + "=" * 65)
        log.info(f"🎉 Pipeline COMPLETE in {elapsed:.0f}s")
        log.info(f"   📺 YouTube:   {short_url}")
        log.info(f"   📱 TikTok:    {social.get('tiktok', 'skipped')}")
        log.info(f"   📷 Instagram: {social.get('instagram', 'skipped')}")
        log.info(f"   📌 Title:     {seo.title}")
        log.info("=" * 65 + "\n")

        _save_run_record(topic, seo, video_id, short_url, elapsed)
        return True


    except Exception as e:
        log.error(f"❌ Pipeline FAILED: {type(e).__name__}: {e}")
        log.debug(traceback.format_exc())
        return False

    finally:
        # Clean up temp audio to save disk space (keep final video)
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
                log.debug(f"🧹 Cleaned up temp audio: {audio_path.name}")
            except Exception:
                pass


def run_batch():
    """Run SHORTS_PER_RUN pipelines sequentially in one scheduler tick."""
    n = config.SHORTS_PER_RUN
    log.info(f"📦 Starting batch: {n} Short(s) to produce")

    success = 0
    for i in range(n):
        if n > 1:
            log.info(f"\n[{i+1}/{n}] Starting Short production...")
        if run_pipeline():
            success += 1
        if i < n - 1:
            time.sleep(30)  # Brief pause between uploads

    log.info(f"✅ Batch complete: {success}/{n} Shorts uploaded successfully")


def _save_run_record(topic, seo, video_id, url, elapsed):
    """Append a record of this run to logs/run_history.jsonl"""
    import json
    record = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "title": seo.title,
        "video_id": video_id,
        "url": url,
        "elapsed_seconds": round(elapsed, 1),
        "niche": config.CONTENT_NICHE,
    }
    history_file = config.LOGS_DIR / "run_history.jsonl"
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Agent — Automated Short-form video production"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit (no scheduler)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start scheduler without an immediate run",
    )
    args = parser.parse_args()

    # ── Print startup banner ───────────────────────────────────────────────────
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("=" * 62)
    print("  YouTube Shorts Agent -- Automated viral content pipeline")
    print("=" * 62)
    log.info(f"Config: niche={config.CONTENT_NICHE} | "
             f"schedule={config.SCHEDULE_INTERVAL_HOURS}h | "
             f"per_run={config.SHORTS_PER_RUN}")

    if args.once:
        log.info("Mode: Single run")
        run_batch()
        return

    if not args.schedule:
        # Run immediately on startup
        log.info("Running initial batch on startup...")
        run_batch()

    # ── Set up scheduler ──────────────────────────────────────────────────────
    interval = config.SCHEDULE_INTERVAL_HOURS
    log.info(f"⏰ Scheduler started — running every {interval} hours")
    schedule.every(interval).hours.do(run_batch)

    while True:
        schedule.run_pending()
        next_run = schedule.next_run()
        if next_run:
            wait = (next_run - datetime.now()).total_seconds()
            log.info(f"💤 Next run in {wait/3600:.1f}h ({next_run.strftime('%H:%M')})")
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    main()
