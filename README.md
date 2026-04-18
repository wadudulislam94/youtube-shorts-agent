# 🎬 YouTube Shorts Agent — Free Edition

A fully automated pipeline that discovers trending topics, writes viral scripts, generates
Microsoft neural voiceovers, transcribes word-level subtitles locally, renders karaoke-subtitle
videos, and uploads them to YouTube — all on a schedule. **Total cost: $0.**

---

## 💰 Cost Breakdown

| Component | Tool | Cost |
|---|---|---|
| Script & SEO | Google Gemini 1.5 Flash | ✅ FREE (1,500 req/day) |
| TTS Voiceover | Microsoft Edge Neural TTS | ✅ FREE (no key needed) |
| Word Timestamps | OpenAI Whisper (local) | ✅ FREE (runs on CPU) |
| Background Videos | Pixabay API | ✅ FREE (email signup) |
| Trending Topics | Reddit JSON + RSS Feeds | ✅ FREE (no key needed) |
| YouTube Upload | YouTube Data API v3 | ✅ FREE (Google account) |
| **Total** | | **$0.00 / month** |

---

## 🚀 Setup (15 minutes total)

### Step 1 — Run `SETUP.bat`
Double-click `SETUP.bat`. It creates a Python virtual environment and installs everything.

> **Requires Python 3.10+** — download at [python.org](https://www.python.org/downloads/)
> **Requires ffmpeg** — run in terminal: `winget install ffmpeg`

---

### Step 2 — Get Gemini API Key (5 minutes, free)

1. Go to → **https://aistudio.google.com/app/apikey**
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the key → paste into `.env` as `GEMINI_API_KEY=...`

> No credit card required. Free tier = 1,500 requests/day.

---

### Step 3 — Get Pixabay API Key (2 minutes, free)

1. Go to → **https://pixabay.com/api/docs/**
2. Click **"Get Your API Key"** at the top
3. Enter your email and create an account
4. Copy your API key → paste into `.env` as `PIXABAY_API_KEY=...`

> Completely free. Unlimited requests.

---

### Step 4 — YouTube OAuth (8 minutes, uses your Google account)

1. Go to → **https://console.cloud.google.com**
2. Click **"New Project"** → name it `Shorts Agent` → Create
3. In the left menu: **APIs & Services → Library**
4. Search **"YouTube Data API v3"** → Click it → **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **"+ Create Credentials" → "OAuth 2.0 Client IDs"**
7. Configure consent screen first if prompted:
   - User type: **External** → Create
   - App name: `Shorts Agent`, User support email: your email → Save
   - Under **"Test users"** → Add your Google email → Save
8. Back at Create Credentials:
   - Application type: **Desktop app**
   - Name: `Shorts Agent` → Create
9. Click **"Download JSON"** on the credential you just created
10. Rename the downloaded file to `client_secrets.json`
11. Copy it to: `credentials/client_secrets.json`

---

### Step 5 — Add a Font (Optional but recommended)

1. Go to → **https://fonts.google.com/specimen/Montserrat**
2. Click **"Download family"**
3. Extract the zip and find `Montserrat-ExtraBold.ttf`
4. Copy it to: `assets/fonts/Montserrat-ExtraBold.ttf`

> Without a font, the agent falls back to Windows system fonts (Arial Bold).

---

### Step 6 — Configure `.env`

Open `.env` and set your niche:
```env
GEMINI_API_KEY=AIza...your_key_here...
PIXABAY_API_KEY=12345678-abcdef...
CONTENT_NICHE=facts        # facts | finance | motivation | history | tech
SHORTS_PER_RUN=1
SCHEDULE_INTERVAL_HOURS=6
TTS_VOICE=random
WHISPER_MODEL=base
```

---

### Step 7 — Test Run

Double-click **`RUN_ONCE.bat`**

- **First time only**: A browser opens for Google OAuth login. Sign in → click Allow.
- Watch the terminal — the full pipeline runs and uploads one Short to your channel.
- Check `logs/run_history.jsonl` for the video URL.

---

### Step 8 — Start Scheduled Agent

Double-click **`START.bat`**

The agent runs immediately, then repeats every 6 hours (= 4 Shorts/day).

---

## 📁 Project Structure

```
youtube-shorts-agent/
├── main.py                        # Orchestrator + scheduler
├── config.py                      # All settings (reads .env)
├── logger.py                      # Colorized logging
├── .env                           # Your keys (NEVER share this)
├── requirements.txt
│
├── modules/
│   ├── trend_finder.py            # Reddit JSON + RSS (no key)
│   ├── script_generator.py        # Gemini 1.5 Flash (free)
│   ├── tts_generator.py           # edge-tts Microsoft neural (free)
│   ├── subtitle_generator.py      # faster-whisper local (free)
│   ├── video_builder.py           # MoviePy + Pixabay (free)
│   ├── seo_generator.py           # Gemini 1.5 Flash (free)
│   └── uploader.py                # YouTube Data API v3 (free)
│
├── assets/
│   ├── fonts/                     # Drop Montserrat-ExtraBold.ttf here
│   └── whisper_models/            # Auto-downloaded on first run
│
├── output/final/                  # ← Your rendered Shorts live here
├── credentials/client_secrets.json  # ← YouTube OAuth file
└── logs/run_history.jsonl         # All upload records
```

---

## ⚙️ Available Niches

| Niche | Sources | Background Style |
|---|---|---|
| `facts` | r/todayilearned, r/interestingasfuck | Satisfying nature/abstract |
| `finance` | r/personalfinance, r/investing | City skyline aerial |
| `motivation` | r/GetMotivated, r/selfimprovement | Sunrise mountain |
| `history` | r/history, r/AskHistorians | Ancient ruins cinematic |
| `tech` | r/technology, r/Futurology | Futuristic neon abstract |

---

## 🎙️ Available TTS Voices

Set `TTS_VOICE=random` to randomize per video (recommended for uniqueness), or pick one:

| Voice ID | Style |
|---|---|
| `en-US-AriaNeural` | Female, conversational, energetic |
| `en-US-ChristopherNeural` | Male, deep, authoritative |
| `en-US-GuyNeural` | Male, friendly, natural |
| `en-US-JennyNeural` | Female, warm, clear |
| `en-GB-RyanNeural` | British male, engaging |
| `en-US-DavisNeural` | Male, casual, youthful |
| `en-AU-NatashaNeural` | Australian female, upbeat |

---

## 🐛 Troubleshooting

| Error | Fix |
|---|---|
| `GEMINI_API_KEY not set` | Paste your key in `.env` |
| `PIXABAY_API_KEY not set` | Paste your key in `.env` |
| `client_secrets.json not found` | Complete YouTube OAuth Step 4 |
| `moviepy write_videofile` hangs | Run `winget install ffmpeg` in terminal |
| Whisper model download slow | First run only (~74MB). Wait for it. |
| `edge-tts` ConnectionError | Check internet connection; edge-tts needs network |
| YouTube quota exceeded | 10,000 units/day free; each upload = ~1,600 units = max 6/day |

---

## 💡 Tips for Faster Monetization

- Post **3-4 Shorts/day** (`SHORTS_PER_RUN=1`, `SCHEDULE_INTERVAL_HOURS=6`)
- Stay in **one niche** for 30 days — algorithm rewards consistency
- After uploading, open YouTube Studio and add **trending audio** from their library
- **Reply to every comment** in the first 60 minutes after posting
- You need **1,000 subscribers + 10M Shorts views in 90 days** to monetize
