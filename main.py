import base64
import hashlib
import hmac
import json
import os
import re

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

# Actual column headers from row 4 of each sheet (multi-line headers joined with space)
SHEET_COLUMNS = {
    "1. Feed Water & Digester": [
        "Date (DD/MM/YY)", "Shift A / B / C", "Time (HH:MM)", "Operator Name",
        "Feed Water Flow (m³/hr)", "Pump Start Time", "Pump Stop Time",
        "pH Before MCL", "pH After MCL", "Temp Before MCL (°C)", "Temp After MCL (°C)",
        "COD Water Inlet (mg/L)", "COD Water Outlet (mg/L)", "COD Removal Efficiency (%)",
        "CT Inlet Temp (°C)", "CT Outlet Temp (°C)", "CT Fan Status",
        "Feed to Digester (m³/hr)", "Pond Level (m)", "Pond Temp (°C)", "Pond pH",
        "pH Correction Dosing (L/hr)", "Digester Temp (°C)", "Digester pH",
        "OLR (kg COD/m³/d)", "HRT (days)", "Recirc. Flow (m³/hr)",
        "VFA (mg/L)", "Alkalinity (mg/L CaCO₃)", "VFA / Alk Ratio",
        "Effluent COD (mg/L)", "COD Removal (%)", "Effluent pH",
        "Cover / Membrane Condition", "Cover Pressure (mbar)",
        "Remarks / Issues / Actions Taken",
    ],
    "2. Gas Treatment": [
        "Date (DD/MM/YY)", "Time (HH:MM)", "Shift A / B / C", "Operator Name",
        "Gas Flow Before Scrubber (m³/hr)", "Gas Flow Before MTU / Engine (m³/hr)",
        "Gas Holder Level (%)", "Gas Holder Pressure (mbar)", "Flare Status (On/Off)",
        "Gas Temp Inlet (°C)", "Gas Temp Outlet (°C)", "Gas Humidity (%RH)",
        "Blower 1 Pressure (mbar)", "Blower 1 Flow (m³/hr)",
        "Blower 2 Pressure (mbar)", "Blower 2 Flow (m³/hr)",
        "Blower Suction Pressure (mbar)", "Gas Return Valve Position (%)",
        "Coolant Pressure Hot Side (bar)", "Coolant Pressure Cool Side (bar)",
        "Water Pressure 1 Open Valve (bar)", "Water Pressure 1 Baseline (bar)",
        "Differential Pressure (mbar)",
        "Inlet H₂S (ppm)", "Outlet H₂S (ppm)", "H₂S Removal Eff. (%)",
        "pH Supply Tank", "pH MUW Tank", "pH Inside Scrubber",
        "Scrubber Temp (°C)", "Liquid Flow (L/min)", "Air Injection (m³/hr)",
        "ΔP Across Bed (mbar)", "Sump Level (%)",
        "CH₄ (%)", "CO₂ (%)", "O₂ (%)", "CO (ppm)",
        "H₂S post-scrub (ppm)", "LHV (MJ/m³)", "Gas Quality Index (Pass/Fail)",
        "Remarks / Issues / Actions Taken",
    ],
    "3. Gas Engine (Daily)": [
        "Date (DD/MM/YY)", "Shift A / B / C", "Engine Start Time", "Engine Stop Time",
        "Total Op. Hours This Day (hrs)", "Operator Name",
        "Flow Meter Before Engine (m³/hr)", "Gas Inlet Pressure (kPa)",
        "CH₄ (%)", "O₂ (%)", "CO₂ (%)", "H₂S (ppm)", "Gas Humidity (%RH)",
        "kWh Generated — Peak", "kWh Generated — Off-Peak", "Total kWh Generated (1 Day)",
        "Engine Speed (rpm)",
        "No N&S Alarm (Red)", "Check A Alarm (Yellow)", "No MCC Overload",
        "HRSG System ON", "Hot Water System ON",
        "Gas Pressure Before Pre-GT (bar)", "Gas Pressure After Pre-GT (mbar)",
        "No Gas Leaks", "Fuel Temp (°C)",
        "Set Power (kW)", "Actual Power (kW)", "Power Factor", "Voltage (V)", "Frequency (Hz)",
        "Lube Oil Temp (°C)", "Lube Oil Inlet Pressure (bar)",
        "P-Diff Lube Oil (bar)", "Crankcase Pressure (mbar)", "Oil Level OK",
        "JW Inlet Temp (°C)", "JW Inlet Pressure (bar)",
        "JW Outlet Temp (°C)", "JW Outlet Pressure (bar)", "JW 3-Way Valve (%)",
        "IC Inlet Temp (°C)", "IC Inlet Pressure (bar)",
        "IC Outlet Temp (°C)", "IC Outlet Pressure (bar)", "IC 3-Way Valve (%)",
        "Air Temp T-A (°C)", "Air Temp T-B (°C)",
        "Air Press P-A (mbar)", "Air Press P-B (mbar)",
        "Gas Temp To Engine (°C)", "Gas Press To Engine (kPa)", "Gas Valve Open (%)",
        "Charge Mix Temp (°C)", "Charge Press Before Throttle (bar)",
        "Charge Press A side (bar)", "Charge Press B side (bar)",
        "Throttle A (%)", "Throttle B (%)", "Mix Throttle Bypass (%)",
        "Avg Exhaust Temp (°C)", "Exhaust After Turbo A (°C)", "Exhaust After Turbo B (°C)",
        "Bearing Temp A (°C)", "Bearing Temp B (°C)",
        "Winding U1 (°C)", "Winding V1 (°C)", "Winding W1 (°C)",
        "Fault / Alarm Description", "Actions Taken",
    ],
    "4. Engine Stop Check": [
        "Date (DD/MM/YY)", "Total Run Hours (cumulative)", "Operator Name",
        "HT System Pressure (bar)", "HT Pump & Equipment OK",
        "HT Pipes & Joints No Leak", "HT Valves Direction OK",
        "LT System Pressure (bar)", "LT Pump & Equipment OK",
        "LT Pipes & Joints No Leak", "LT Valves Direction OK",
        "Air Filter No Blockage", "Air Filter Not Damaged",
        "No Oil Leaks", "Lube Valves OK", "Reserve Oil Level (litres)",
        "Drain Valve Direction OK", "Hose Water Level (cm)",
        "Battery Clean", "Clamp & Terminal OK", "Wiring OK", "Acid Level OK",
        "Main Valve Fully Open",
        "Pressure Before Pre-GT (bar)", "Pressure After Pre-GT (mbar)",
        "No Gas Leaks", "Wiring & Equipment OK",
        "Engine Room Clean & Clear", "Alarms Cleared", "No MCC Overload",
        "Remarks / Issues / Actions Taken",
    ],
    "5. Weekly Engine Check": [
        "Week Start (DD/MM/YY)", "Week End (DD/MM/YY)", "Operator Name",
        "Running Hours This Week (hrs)", "Power Generated This Week (MW)",
        "No. of Engine Starts (times)",
        "Battery Clean", "Distilled Water Level OK (10–15mm above plate)",
        "Specific Gravity (kg/L)", "SG Status (Well / Semi / Disc)",
        "Pre-Air Filter Cleaned", "Filter Mounting Points OK",
        "Last Air Filter Change Date",
        "Oil Top-up Count From Panel (times)", "Reserve Tank Level (litres)",
        "Oil Added to Reserve (litres)", "Last Oil Change Date",
        "Last Oil Change At Hour (hrs)", "Next Oil Change Due At (hrs)",
        "Engine & Area Cleaned",
        "Remarks / Issues / Actions Taken",
    ],
}

SHEET_NAMES = list(SHEET_COLUMNS.keys())

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def verify_line_signature(body: bytes, signature: str) -> bool:
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
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
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # Build column lists for prompt
    sheet_col_info = ""
    for sheet_name, cols in SHEET_COLUMNS.items():
        sheet_col_info += f'\n{sheet_name}:\n  {json.dumps(cols)}\n'

    prompt = f"""You are reading a POME Biogas plant operation form photo.

Identify which of these 5 sheet types the form belongs to:
1. "1. Feed Water & Digester"
2. "2. Gas Treatment"
3. "3. Gas Engine (Daily)"
4. "4. Engine Stop Check"
5. "5. Weekly Engine Check"

Each sheet has these exact column headers:
{sheet_col_info}

FIELD NAME MAPPINGS for "2. Gas Treatment" (Scrubber form / ตารางตรวจสอบ ระบบ Scrubber):
CRITICAL — read each label carefully from left column of the paper, then find the value:
- "Gen (MW)" → DO NOT USE. This is generator power, skip this row entirely, do not put its value anywhere.
- "Gas flow (Nm³/h)" → "Gas Flow Before Scrubber (m³/hr)"  [e.g. 921.10, NOT the Gen value]
- "CH₄ outlet (%)" → "CH₄ (%)"
- "CO₂ outlet scrubber (%)" → "CO₂ (%)"
- "O₂ outlet scrubber (%)" → "O₂ (%)"
- "H₂S outlet scrubber (ppm)" → "Outlet H₂S (ppm)"  [NOT Inlet]
- "H₂S inlet scrubber (ppm)" → "Inlet H₂S (ppm)"
- "Pump pressure (bar)" → "Coolant Pressure Hot Side (bar)"
- "Water flow (m³/h) circulate pump" → "Liquid Flow (L/min)"
- "pH ถัง Supply" → "pH Supply Tank"
- "pH ถัง MUW" → "pH MUW Tank"
- "pH (scrubber tank)" → "pH Inside Scrubber"
- "Pressure outlet scrubber (mbar)" → "ΔP Across Bed (mbar)"
- "Different pressure (mbar)" → "Differential Pressure (mbar)"
- "อุณหภูมิขาเข้า/ขาออก Dehumidifier (°C)" → first number → "Gas Temp Inlet (°C)", second number → "Gas Temp Outlet (°C)"
- "Pressure ขาเข้า/ขาออก gas blower (mbar)" → first number → "Blower Suction Pressure (mbar)"

INSTRUCTIONS:
- Read the form and identify the sheet type from the title/header
- If the form has time-based columns (e.g. 10:00, 14:00, 18:00, 22:00, 2:00, 6:00 น.):
  Return ONE row object for EVERY time slot column shown in the header (even if most values are dash/null)
- Apply the field name mappings above — paper labels differ from sheet column names
- Read numbers carefully — e.g. 921.10 is nine-hundred-twenty-one point ten, NOT 92.10
- Use null for missing/blank/illegible values and dashes ("-")
- Keys in each row object MUST be exact column header strings from the list above

Return ONLY valid JSON in this format (no markdown, no explanation):
{{"sheet": "<exact sheet name>", "rows": [{{"col_name": "value", ...}}, ...]}}

For non-time-based forms (Engine Stop Check, Weekly Engine Check), return a single row in "rows".
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
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
    print(f"Claude raw response (first 800 chars): {text[:800]}")

    # Strip markdown code fences if present
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

    # Find outermost JSON object
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        text = brace_match.group(0)

    return json.loads(text)


def append_rows_to_sheet(sheet_name: str, rows: list[dict]):
    service = get_sheets_service()

    # Use hardcoded column order (matches sheet column order)
    headers = SHEET_COLUMNS[sheet_name]
    print(f"Using columns (first 5): {headers[:5]}")

    all_values = []
    for row_data in rows:
        row = []
        for h in headers:
            val = row_data.get(h)
            if val is None:
                row.append("")
            else:
                row.append(str(val))
        all_values.append(row)

    if all_values:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{sheet_name}'!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": all_values},
        ).execute()
        print(f"Appended {len(all_values)} row(s) to sheet: {sheet_name}")


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
            rows = result.get("rows", [])

            if sheet_name not in SHEET_NAMES:
                print(f"Unknown sheet detected: {sheet_name}")
                continue

            if not rows:
                print(f"No rows extracted for sheet: {sheet_name}")
                continue

            append_rows_to_sheet(sheet_name, rows)

        except Exception as e:
            import traceback
            print(f"Error processing image {message_id}: {e}")
            print(traceback.format_exc())

    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "running"}
