import asyncio
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
        # Gas Flow
        "Gas Flow Before Scrubber (m³/hr)", "Gas Flow Before MTU / Engine (m³/hr)",
        "Flare Status (On/Off)",
        # Dehumidifier
        "Gas Temp Inlet (°C)", "Gas Temp Outlet (°C)",
        "Coolant Pressure Hot Side (bar)", "Coolant Pressure Cool Side (bar)",
        "Gas Humidity (%RH)",
        # Blower
        "Blower 1 Pressure (mbar)", "Blower 1 Flow (m³/hr)",
        "Blower 2 Pressure (mbar)", "Blower 2 Flow (m³/hr)",
        "Blower Suction Pressure (mbar)", "Gas Return Valve Position (%)",
        # Bio-Scrubber
        "Inlet H₂S (ppm)", "Outlet H₂S (ppm)", "H₂S Removal Eff. (%)",
        "pH Supply Tank", "pH MUW Tank", "pH Inside Scrubber",
        "Circulate Pump Pressure (bar)", "Circulate Pump Flow (m³/h)",
        "Effluent Pump Flow (LPM)",
        "Air Injection Valve (% open)", "Scrubber ΔP (mbar)", "Sump Level (%)",
        # Gas Quality
        "CH₄ (%)", "CO₂ (%)", "O₂ (%)", "H₂S post-scrub (ppm)",
        "Gas Quality Index (Pass/Fail)",
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

# --- Multi-page batching --------------------------------------------------
# Some paper forms (e.g. "3. Gas Engine (Daily)") span multiple photos/pages
# that together make up ONE report. LINE delivers each photo as its own
# webhook event, so without batching each photo gets written as its own
# incomplete set of rows. Instead, we buffer photos per LINE source
# (group/room/user) and wait BATCH_DELAY_SECONDS after the last photo before
# processing the whole batch together and merging into complete rows.
BATCH_DELAY_SECONDS = 20

# source_id -> {"images": [bytes, ...], "task": asyncio.Task | None}
PENDING_BATCHES: dict[str, dict] = {}

# LINE retries webhook delivery if it doesn't get a fast-enough 200 response.
# Track message IDs we've already scheduled so a retried delivery doesn't
# process (and write) the same photo twice.
SEEN_MESSAGE_IDS: set[str] = set()
SEEN_MESSAGE_IDS_MAX = 2000


def merge_extractions(extractions: list[dict]) -> dict:
    """Merge multiple Claude extraction results (one per photo/page of the
    same report) into a single set of complete rows.

    Rows are combined positionally: row 0 from every extraction is assumed to
    be the same time slot, row 1 the same time slot, etc. (this matches how
    the forms lay out repeated hourly/shift columns identically on every
    page). Most fields only appear on ONE page, so there's nothing to
    resolve. But a few fields (Date, Shift, Operator Name, etc.) are repeated
    on every page's header — if pages disagree on those (e.g. one page's
    date was misread), we pick the value the MAJORITY of pages agree on
    instead of just whichever extraction happened to run first. Ties keep
    the first-seen value.
    """
    from collections import Counter

    sheet_names_seen = [e.get("sheet") for e in extractions if e.get("sheet")]
    if len(set(sheet_names_seen)) > 1:
        print(f"Warning: batch had mismatched sheet types: {sheet_names_seen}")
    sheet_name = sheet_names_seen[0] if sheet_names_seen else None

    max_rows = max((len(e.get("rows", [])) for e in extractions), default=0)

    # (row_index, column_key) -> list of non-null values seen, in the order
    # their extraction was processed
    candidates: dict[tuple[int, str], list] = {}
    for e in extractions:
        for i, row in enumerate(e.get("rows", [])):
            if i >= max_rows:
                continue
            for k, v in row.items():
                if v is None or v == "":
                    continue
                candidates.setdefault((i, k), []).append(v)

    merged_rows = [dict() for _ in range(max_rows)]
    for (i, k), values in candidates.items():
        if len(values) > 1 and len(set(values)) > 1:
            # Pages disagree on this field — take the majority vote.
            # Counter.most_common() is stable, so ties fall back to the
            # first-seen value.
            winner = Counter(values).most_common(1)[0][0]
            if len(set(values)) > 1:
                print(f"Row {i} field '{k}' disagreed across pages {values} -> using {winner}")
        else:
            winner = values[0]
        merged_rows[i][k] = winner

    return {"sheet": sheet_name, "rows": merged_rows}


def split_by_report(extractions: list[dict]) -> list[list[dict]]:
    """Guard against a batch accidentally containing pages from more than one
    day's report (e.g. a worker sends two different daily reports back to
    back and both land inside the same debounce window).

    Groups extractions by the Date value on their first row. A date shared by
    2+ pages is treated as a real, distinct report. A date seen on only ONE
    page is treated as a likely misread of one of the real reports and folded
    into the largest one, rather than becoming its own incomplete report
    (this preserves the existing behavior for the common case where one page
    out of several just misread its date).
    """
    date_col = "Date (DD/MM/YY)"
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for e in extractions:
        rows = e.get("rows", [])
        date_val = rows[0].get(date_col) if rows else None
        key = str(date_val) if date_val else "__unknown__"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e)

    real_reports = [k for k in order if len(groups[k]) >= 2]

    if len(real_reports) <= 1:
        # Zero or one dominant date shared by multiple pages -> treat the
        # whole batch as one report (existing behavior).
        return [extractions]

    print(f"Batch contains pages from {len(real_reports)} different reports (by date): {real_reports}")
    result = {k: list(groups[k]) for k in real_reports}
    largest_key = max(real_reports, key=lambda k: len(groups[k]))
    for k in order:
        if k not in real_reports:
            print(f"Folding {len(groups[k])} page(s) dated '{k}' into report '{largest_key}' (likely misread, not enough pages to be its own report)")
            result[largest_key].extend(groups[k])

    return [result[k] for k in real_reports]


async def process_batch(source_id: str):
    try:
        await asyncio.sleep(BATCH_DELAY_SECONDS)
    except asyncio.CancelledError:
        # A newer photo arrived and rescheduled the timer; let the new task run.
        return

    batch = PENDING_BATCHES.pop(source_id, None)
    if not batch or not batch["images"]:
        return

    images = batch["images"]
    print(f"Processing batch of {len(images)} image(s) for source {source_id}")

    extractions = []
    for img in images:
        try:
            extractions.append(extract_form_data(img))
        except Exception as e:
            import traceback
            print(f"Error extracting one image in batch: {e}")
            print(traceback.format_exc())

    if not extractions:
        print("No successful extractions in batch")
        return

    for report_extractions in split_by_report(extractions):
        merged = merge_extractions(report_extractions)
        sheet_name = merged.get("sheet")
        rows = merged.get("rows", [])

        if sheet_name not in SHEET_NAMES:
            print(f"Unknown sheet detected in batch: {sheet_name}")
            continue
        if not rows:
            print(f"No rows extracted for sheet: {sheet_name}")
            continue

        rows = fix_date(rows)
        append_rows_to_sheet(sheet_name, rows)


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

FIELD NAME MAPPINGS for "2. Gas Treatment" (redesigned form — labels match sheet columns):
CRITICAL — read each label carefully from the left column of the paper, then find the value:
- "Gen (MW)" → DO NOT USE. Generator power — skip entirely, never put its value in any column.
- "Gas Flow Before Scrubber" → "Gas Flow Before Scrubber (m³/hr)"
- "Gas Flow Before MTU / Engine" → "Gas Flow Before MTU / Engine (m³/hr)"
- "Flare Status" → "Flare Status (On/Off)"
- "Gas Temp Inlet" → "Gas Temp Inlet (°C)"
- "Gas Temp Outlet" → "Gas Temp Outlet (°C)"
- "Coolant Pressure Hot Side" → "Coolant Pressure Hot Side (bar)"  [dehumidifier coolant — NOT scrubber pump]
- "Coolant Pressure Cool Side" → "Coolant Pressure Cool Side (bar)"
- "Gas Humidity" → "Gas Humidity (%RH)"  [may be blank — no equipment yet, output null]
- "Blower 1 Pressure" → "Blower 1 Pressure (mbar)"
- "Blower 1 Flow" → "Blower 1 Flow (m³/hr)"
- "Blower 2 Pressure" → "Blower 2 Pressure (mbar)"
- "Blower 2 Flow" → "Blower 2 Flow (m³/hr)"
- "Blower Suction Pressure" → "Blower Suction Pressure (mbar)"
- "Gas Return Valve Position" → "Gas Return Valve Position (%)"
- "Inlet H₂S" → "Inlet H₂S (ppm)"  [gas ENTERING the scrubber]
- "Outlet H₂S" → "Outlet H₂S (ppm)"  [gas LEAVING the scrubber — NOT Inlet]
- "H₂S Removal Eff." → "H₂S Removal Eff. (%)"  [shaded on form — read if filled, null if blank]
- "pH Supply Tank" → "pH Supply Tank"
- "pH MUW Tank" → "pH MUW Tank"
- "pH Inside Scrubber" → "pH Inside Scrubber"
- "Circulate Pump Pressure" → "Circulate Pump Pressure (bar)"  [scrubber circulate pump — NOT coolant]
- "Circulate Pump Flow" → "Circulate Pump Flow (m³/h)"
- "Effluent Pump Flow" → "Effluent Pump Flow (LPM)"
- "Air Injection Valve" → "Air Injection Valve (% open)"
- "Scrubber ΔP" → "Scrubber ΔP (mbar)"
- "Sump Level" → "Sump Level (%)"  [optional — null if blank]
- "CH₄" → "CH₄ (%)"
- "CO₂" → "CO₂ (%)"
- "O₂" → "O₂ (%)"
- "H₂S post-scrub" → "H₂S post-scrub (ppm)"
- "Gas Quality Index" → "Gas Quality Index (Pass/Fail)"

Old Thai-label form (backward compatibility):
- "Gas flow (Nm³/h)" → "Gas Flow Before Scrubber (m³/hr)"
- "H₂S inlet scrubber (ppm)" → "Inlet H₂S (ppm)"
- "H₂S outlet scrubber (ppm)" → "Outlet H₂S (ppm)"  [NOT Inlet]
- "CH₄ outlet (%)" → "CH₄ (%)"
- "CO₂ outlet scrubber (%)" → "CO₂ (%)"
- "O₂ outlet scrubber (%)" → "O₂ (%)"
- "Pump pressure (bar)" → "Circulate Pump Pressure (bar)"  [scrubber circulate pump]
- "Water flow (m³/h) circulate pump" → "Circulate Pump Flow (m³/h)"
- "pH ถัง Supply" → "pH Supply Tank"
- "pH ถัง MUW" → "pH MUW Tank"
- "pH (scrubber tank)" → "pH Inside Scrubber"
- "Pressure outlet scrubber (mbar)" or "Different pressure (mbar)" → "Scrubber ΔP (mbar)"
- "Air injection (% valve)" → "Air Injection Valve (% open)"
- "อุณหภูมิขาเข้า/ขาออก Dehumidifier (°C)" → first number → "Gas Temp Inlet (°C)", second → "Gas Temp Outlet (°C)"

INSTRUCTIONS:
- Read the form and identify the sheet type from the title/header
- Read the date carefully from the top of the form — it is in DD/MM/YY format (Thai Buddhist year, e.g. 28/6/69)
- If the form has time-based columns (e.g. 10:00, 14:00, 18:00, 22:00, 2:00, 6:00 น.):
  Return ONE row object for EVERY time slot column shown in the header (even if most values are dash/null)
- The time-slot label itself (e.g. "10:00", "22:00") is ONLY a column header on the paper telling you
  which reading to use for that row — it is NOT a data value. Do NOT write it into any sheet column,
  and especially NEVER write it into "Engine Start Time" or "Engine Stop Time" — those two columns mean
  the actual time the engine was started/stopped for the day (usually not shown per time-slot reading;
  leave them null unless the paper explicitly labels a value as engine start/stop time).
- Apply the field name mappings above — paper labels differ from sheet column names
- STRICT RULE: For each time slot, only read the value from the EXACT row labeled on the paper.
  If a row shows "-" or is blank for that time slot, output null for that column.
  NEVER fill a sheet column with a value from a different paper row just because the correct row is empty.
  Example: if "Gas flow (Nm³/h)" is "-" at 10:00, then "Gas Flow Before Scrubber (m³/hr)" must be null — do not use Pump pressure or any other row's value.
- KNOWN TRAP in "3. Gas Engine (Daily)": on the paper, "ตรวจเช็คอุณหภูมิของเชื้อเพลิง" (fuel temperature, → "Fuel Temp (°C)")
  sits directly above "ตรวจเช็คค่าความชื้นของเชื้อเพลิง" (fuel humidity, → "Gas Humidity (%RH)"), and the humidity row is
  normally all dashes (no humidity sensor installed). Because these two rows sit right next to each other, do NOT copy
  the temperature row's readings into "Gas Humidity (%RH)" just because the humidity row is blank — read each row
  independently. "Fuel Temp (°C)" and "Gas Humidity (%RH)" must never end up holding the same set of values for a
  report unless both were genuinely read from their own separate paper rows.
- Read numbers carefully — e.g. 921.10 is nine-hundred-twenty-one point ten, NOT 92.10
- Use null for missing/blank/illegible values and dashes ("-")
- Keys in each row object MUST be exact column header strings from the list above
- CRITICAL for valid JSON: every non-null value MUST be wrapped in double quotes as a JSON string,
  even if it looks like a plain number (e.g. write "60.8" not 60.8). This applies even to ambiguous
  or partially illegible handwriting (e.g. "60.A") — always quote it as a string rather than emitting
  it unquoted, otherwise the JSON becomes invalid and the ENTIRE photo's data is discarded.

Return ONLY valid JSON in this format (no markdown, no explanation):
{{"sheet": "<exact sheet name>", "rows": [{{"col_name": "value", ...}}, ...]}}

For non-time-based forms (Engine Stop Check, Weekly Engine Check), return a single row in "rows".
"""

    # The instructions/column-list/field-mapping text above is identical on
    # EVERY call (nothing in it depends on the photo) but was previously sent
    # fresh, uncached, on every single request — full price, every photo.
    # Moving it into `system` with a cache_control breakpoint lets Anthropic
    # cache it: only the photo (always different) is sent as fresh, uncached
    # content in the user turn. Cache breakpoints only cache a stable PREFIX,
    # so the static text has to be the thing marked for caching, not the
    # image. Ephemeral cache entries last 5 minutes, so within one 3-photo
    # report batch (photos processed roughly a minute apart) the 2nd and 3rd
    # calls should hit the cache from the 1st call's write.
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=[
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
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
                    # Moving the instructions into `system` (above) caused Claude to
                    # narrate its reading step-by-step in plain English before ever
                    # emitting JSON ("I need to analyze this form carefully... Let me
                    # read each row...") instead of responding with JSON only. That
                    # happened to still parse (the JSON showed up eventually and the
                    # brace-matching regex below found it), but output ballooned to
                    # 6000+ tokens per photo (versus ~2000-3000 before — eating most
                    # of the input-side savings from caching) and burned enough of
                    # the max_tokens budget that a longer form risks truncating
                    # before the JSON ever appears, which would silently drop the
                    # whole photo again. This tiny uncached reminder right before
                    # generation is what restores strict JSON-only output.
                    {
                        "type": "text",
                        "text": (
                            "Respond with ONLY the JSON object described in the system "
                            "instructions. No explanation, no step-by-step reasoning, no "
                            "narration of what you're reading, no markdown code fences — "
                            "your entire response must be a single valid JSON object, "
                            "starting with { and ending with }."
                        ),
                    },
                ],
            }
        ],
    )

    usage = response.usage
    print(
        f"Token usage: input={usage.input_tokens} output={usage.output_tokens} "
        f"cache_write={getattr(usage, 'cache_creation_input_tokens', 0)} "
        f"cache_read={getattr(usage, 'cache_read_input_tokens', 0)}"
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

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Seen in practice: Claude occasionally emits an ambiguous/illegible
        # reading as a bare unquoted token (e.g. `"CH₄ (%)": 60.A,`)
        # despite the prompt instructing it to always quote values. That's
        # invalid JSON syntax, and previously this exception propagated all
        # the way up and caused the ENTIRE photo's extraction to be silently
        # dropped from the batch (logged as an error but never recovered),
        # which showed up downstream as a whole block of sheet columns being
        # blank for that day even though the paper had the values written.
        # Log the FULL response (not just the 800-char preview) so a repeat
        # of this can be diagnosed without needing the photo resent, then
        # try to auto-repair by quoting bare unquoted tokens and re-parse
        # before giving up.
        print(f"JSON parse failed ({e}). Full response ({len(text)} chars): {text}")

        def _quote_bare_token(m: "re.Match") -> str:
            token = m.group(1)
            if token in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", token):
                return m.group(0)
            return f': "{token}"' + m.group(2)

        repaired = re.sub(r':\s*([^",\[\]{}\s][^,\[\]{}]*?)(\s*[,}\]])', _quote_bare_token, text)
        try:
            result = json.loads(repaired)
            print("JSON repair succeeded after quoting bare token(s)")
            return result
        except json.JSONDecodeError as e2:
            print(f"JSON repair also failed ({e2}); giving up on this image")
            raise


def fix_date(rows: list[dict]) -> list[dict]:
    """Validate date from Claude; replace with today if misread."""
    from datetime import datetime, timezone, timedelta, date as date_type
    tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    buddhist_year = (now.year + 543) % 100  # last 2 digits
    today_str = f"{now.day}/{now.month}/{buddhist_year}"
    today = now.date()

    date_col = "Date (DD/MM/YY)"
    for row in rows:
        existing = row.get(date_col)
        use_today = False
        if existing:
            try:
                parts = str(existing).split("/")
                if len(parts) == 3:
                    d, m, y_be = int(parts[0]), int(parts[1]), int(parts[2])
                    # Convert Buddhist year (2-digit) to Gregorian
                    gregorian_year = (y_be + 2500) - 543  # e.g. 69 → 2569 → 2026
                    parsed = date_type(gregorian_year, m, d)
                    # Accept if within 3 days of today
                    if abs((parsed - today).days) > 3:
                        print(f"Date '{existing}' too far from today → using {today_str}")
                        use_today = True
                else:
                    use_today = True
            except Exception:
                use_today = True
        else:
            use_today = True

        if use_today:
            row[date_col] = today_str
            print(f"Date fixed to {today_str}")
    return rows


def append_rows_to_sheet(sheet_name: str, rows: list[dict]):
    service = get_sheets_service()

    # Use hardcoded column order (matches sheet column order)
    headers = SHEET_COLUMNS[sheet_name]
    print(f"Using columns (first 5): {headers[:5]}")

    date_col = "Date (DD/MM/YY)"

    all_values = []
    for row_data in rows:
        row = []
        for h in headers:
            val = row_data.get(h)
            if val is None:
                row.append("")
            elif h == date_col:
                # Force literal text so Sheets doesn't re-parse the Buddhist-year
                # date string as a Gregorian date (e.g. "7/7/69" was being read as
                # the year 1969 instead of 2026). Leading apostrophe forces text,
                # same as typing it manually in the UI.
                row.append("'" + str(val))
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


async def handle_image_event(message_id: str, source_id: str):
    """Background task: download the photo and add it to the source's pending
    batch. This runs AFTER the webhook has already responded to LINE, so a
    slow image download or busy event loop can never delay the webhook
    response enough to trigger a LINE retry (which previously caused the
    same photos to be processed and written twice)."""
    try:
        image_bytes = download_line_image(message_id)
    except Exception as e:
        import traceback
        print(f"Error downloading image {message_id}: {e}")
        print(traceback.format_exc())
        return

    batch = PENDING_BATCHES.setdefault(source_id, {"images": [], "task": None})
    batch["images"].append(image_bytes)

    # Reset the debounce timer: wait BATCH_DELAY_SECONDS after the most
    # recent photo before processing, so all pages of a multi-photo
    # report arrive before we extract + write anything.
    if batch["task"] is not None:
        batch["task"].cancel()
    batch["task"] = asyncio.create_task(process_batch(source_id))


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

        # Belt-and-suspenders dedup: if this exact message was already
        # scheduled (e.g. a retried webhook delivery), skip it.
        if message_id in SEEN_MESSAGE_IDS:
            print(f"Duplicate webhook delivery for message {message_id}, skipping")
            continue
        SEEN_MESSAGE_IDS.add(message_id)
        if len(SEEN_MESSAGE_IDS) > SEEN_MESSAGE_IDS_MAX:
            for _ in range(100):
                SEEN_MESSAGE_IDS.pop()

        source = event.get("source", {})
        # Group photos by where they came from, so multiple pages of the same
        # report (sent to the same group/room/user) get batched together.
        source_id = (
            source.get("groupId") or source.get("roomId") or source.get("userId") or "unknown"
        )

        # Schedule the download + batching in the background instead of
        # awaiting it here, so we can return "ok" to LINE immediately.
        asyncio.create_task(handle_image_event(message_id, source_id))

    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "running"}
