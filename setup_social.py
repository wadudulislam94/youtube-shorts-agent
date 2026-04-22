"""
setup_social.py — One-Time Social Media Token Setup
─────────────────────────────────────────────────────────────────────────────
Run this ONCE on your local machine to get your TikTok and Instagram tokens.

Usage:
    python setup_social.py

Then copy the printed tokens into GitHub Secrets:
    TIKTOK_ACCESS_TOKEN
    INSTAGRAM_USER_ID
    INSTAGRAM_ACCESS_TOKEN
"""

print("""
╔══════════════════════════════════════════════════════════════════╗
║         SOCIAL MEDIA CROSS-POSTER — ONE-TIME SETUP              ║
╚══════════════════════════════════════════════════════════════════╝

This guide will get you TikTok and Instagram tokens.
Each takes about 5 minutes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 1 — TIKTOK TOKEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 1. Go to: https://developers.tiktok.com/
 2. Log in with your TikTok account → click "Manage Apps" → "Create App"
 3. App name: anything (e.g. "MyAnimeShorts")
 4. Category: "Entertainment" → Submit
 5. In your app settings, enable: "Content Posting API"
 6. Under "Credentials" copy your Client Key and Client Secret
 7. To get an Access Token, use TikTok's OAuth flow:
    https://developers.tiktok.com/doc/oauth-user-access-token-management

 IMPORTANT: After approval (can take 1-3 days), you get:
   TIKTOK_ACCESS_TOKEN = "act.xxxxxxxxxxxxxxxxxxxxxx"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 2 — INSTAGRAM TOKEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 REQUIREMENTS:
   ✅ Instagram account must be "Professional" (Creator or Business)
      → Instagram app → Settings → Account type → Switch to Professional
   ✅ Must be linked to a Facebook Page

 1. Go to: https://developers.facebook.com/
 2. Create App → "Business" type
 3. Add product: "Instagram Graph API"
 4. Go to: Tools → Graph API Explorer
 5. Select your App → Generate User Token
 6. Permissions needed:
      instagram_basic
      instagram_content_publish
      pages_read_engagement
 7. Click "Generate Access Token" → copy the token

 To get a LONG-LIVED token (60 days), run this URL in your browser:
 https://graph.facebook.com/v18.0/oauth/access_token
   ?grant_type=fb_exchange_token
   &client_id=YOUR_APP_ID
   &client_secret=YOUR_APP_SECRET
   &fb_exchange_token=YOUR_SHORT_LIVED_TOKEN

 8. Get your Instagram User ID:
    https://graph.instagram.com/v18.0/me?fields=id,username&access_token=YOUR_TOKEN

 You'll get:
   INSTAGRAM_USER_ID       = "17841xxxxxxxxxx"
   INSTAGRAM_ACCESS_TOKEN  = "EAAxxxxxxxxxx..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 3 — ADD TO GITHUB SECRETS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 1. Go to your repo on GitHub
 2. Settings → Secrets and variables → Actions → New repository secret
 3. Add these 3 secrets:

    Name: TIKTOK_ACCESS_TOKEN
    Value: (your TikTok access token)

    Name: INSTAGRAM_USER_ID
    Value: (your Instagram user ID number)

    Name: INSTAGRAM_ACCESS_TOKEN
    Value: (your Instagram long-lived access token)

 4. Done! The next GitHub Actions run will post to all 3 platforms.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TOKEN REFRESH REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Instagram tokens expire after 60 days.
 Run this URL every 50 days to refresh:
 https://graph.instagram.com/refresh_access_token
   ?grant_type=ig_refresh_token
   &access_token=YOUR_TOKEN

 TikTok tokens expire after 24 hours.
 Use a Refresh Token flow for long-running automation:
 https://developers.tiktok.com/doc/oauth-user-access-token-management
""")
