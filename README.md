# LINE → Claude Vision → Google Sheets Automation

Receives photos of POME Biogas operation forms from a LINE group, reads them with Claude AI, and automatically appends the data to the correct Google Sheet tab.

---

## Setup Steps

### 1. LINE Messaging API

1. Go to https://developers.line.biz and sign in with your LINE account
2. Create a new **Provider**, then create a **Messaging API Channel**
3. In the channel settings:
   - Copy the **Channel Secret** → paste as `LINE_CHANNEL_SECRET` in `.env`
   - Under "Messaging API" tab → Issue a **Channel Access Token** → paste as `LINE_CHANNEL_ACCESS_TOKEN` in `.env`
   - Set **Webhook URL** to: `https://your-railway-url.up.railway.app/webhook`
   - Enable **Use webhook**
   - Disable **Auto-reply messages**
4. Add the bot to your LINE group (invite it like a contact)

### 2. Anthropic API Key

1. Go to https://console.anthropic.com
2. Create an API key
3. Paste as `ANTHROPIC_API_KEY` in `.env`

### 3. Google Sheets Service Account

1. Go to https://console.cloud.google.com
2. Create a new project (or use existing)
3. Enable **Google Sheets API**
4. Go to **IAM & Admin → Service Accounts** → Create a service account
5. Create a JSON key for the service account → download it
6. Open the JSON file, copy the entire contents, paste as `GOOGLE_CREDENTIALS_JSON` in `.env` (all on one line)
7. Open your Google Sheet → Share it with the service account email (e.g. `xxx@your-project.iam.gserviceaccount.com`) as **Editor**

### 4. Deploy to Railway.app

1. Go to https://railway.app and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Push this folder to a GitHub repo first, then connect it
4. In Railway project settings → **Variables** → add all 4 variables from `.env`
5. Railway will auto-detect Python and deploy
6. Copy the public URL from Railway → set it as the LINE Webhook URL (step 1 above)

---

## Local Testing

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with real values
uvicorn main:app --reload --port 8000
```

Use [ngrok](https://ngrok.com) to expose localhost for LINE webhook testing:
```bash
ngrok http 8000
# Copy the https URL → set as LINE webhook URL temporarily
```

---

## How It Works

1. Worker posts a photo of the paper form in the LINE group
2. LINE sends the photo to this server via webhook
3. Server downloads the photo and sends it to Claude (claude-haiku-4-5)
4. Claude reads the form, identifies which of the 5 sheet tabs it belongs to, and extracts all field values as JSON
5. Server appends a new row to the correct Google Sheet tab
