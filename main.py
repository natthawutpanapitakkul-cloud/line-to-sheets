import hashlib
import hmac
import json
import os
import re
import tempfile

import anthropic
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

app = FastAPI()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
SPREADSHEET_ID = "1Tt6VCOK6Wipdl7vKMQFM6I7iPxJ2gACUbxi_vSZskAE"

SHEET_NAMES = [
    "1. Feed Water & Digester",
    "2. Gas Treatment",
    "3. Gas Engine (Daily)",
    "4. Engine Stop Check",
    "5. Weekly Engine Check",
]

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def verify_line_signature(body: bytes, signature: str) -> bool:
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    import base64
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def get_sheets_service():
    creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def download_line_image(message_id: str) -> bytes:
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    response = httpx.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def extract_form_data(image_bytes: bytes) -> dict:
    import base64
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    prompt = f"""You are reading a POME Biogas plant daily operation form photo.

The form belongs to one of these 5 sheet types:
1. "1. Feed Water & Digester" — has fields like Feed Water Flow, pH, COD, Digester Temp, Digester pH, VFA, etc.
2. "2. Gas Treatment" — has fields like Gas Flow, Gas Holder Level, Blower Pressure, H2S, CH4%, CO2%, etc.
3. "3. Gas Engine (Daily)" — has fields like Engine Start/Stop Time, kWh Generated, Engine Speed, Lube Oil Temp, JW Temp, etc.
4. "4. Engine Stop Check" — has fields like HT System Pressure, LT System Pressure, Air Filter, Oil Leaks, Battery, Gas Train, etc.
5. "5. Weekly Engine Check" — has fields like Running Hours This Week, Power Generated, Battery SG, Oil Top-up Count, etc.

Instructions:
- Read the form title/header to identify which sheet type this is
- Extract every readable field value
- Return ONLY a valid JSON object with two keys:
  "sheet": the exact sheet name from the list above
  "data": an object where keys match the column headers exactly and values are the extracted values (use null for blank/illegible fields)

Return only the JSON, no explanation."""

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    text = response.content[0].text.strip()
    print(f"Claude raw response (first 500 chars): {text[:500]}")

    # Try 1: strip markdown code block
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

    # Try 2: find the outermost { ... } block
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        text = brace_match.group(0)

    return json.loads(text)


def append_to_sheet(sheet_name: str, data: dict):
    service = get_sheets_service()
    # Get existing headers from row 1
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"'{sheet_name}'!1:1")
        .execute()
    )
    headers = result.get("values", [[]])[0]

    # Build row in header order
    row = [str(data.get(h, "")) if data.get(h) is not None else "" for h in headers]

    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_line_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)

    for event in payload.get("events", []):
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "image":
            continue

        message_id = message["id"]
        try:
            image_bytes = download_line_image(message_id)
            result = extract_form_data(image_bytes)
            sheet_name = result.get("sheet")
            form_data = result.get("data", {})

            if sheet_name not in SHEET_NAMES:
                print(f"Unknown sheet detected: {sheet_name}")
                continue

            append_to_sheet(sheet_name, form_data)
            print(f"Appended to sheet: {sheet_name}")

        except Exception as e:
            print(f"Error processing image {message_id}: {e}")

    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "running"}
