"""
BPO Ops Superflow — FastMCP Server

An isolated microservice that handles external tool execution for the BPO pipeline.
Exposes tools for fetching Google Sheets data (transcripts, leave, agent metrics),
PII-redaction middleware, and Gmail-based email notifications.
"""

import base64
import csv
import io
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Server Initialization
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="BPO-MCP-Server",
    instructions=(
        "This MCP server provides tools for the BPO Ops Superflow pipeline. "
        "All transcript data returned is PII-redacted. Do not attempt to bypass redaction."
    ),
)


# ---------------------------------------------------------------------------
# Google API Authentication (Gmail only — Sheets uses public CSV URL)
# ---------------------------------------------------------------------------
_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SERVER_DIR)

CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH",
    os.path.join(_PROJECT_ROOT, "credentials.json"),
)
TOKEN_PATH = os.getenv(
    "GOOGLE_TOKEN_PATH",
    os.path.join(_PROJECT_ROOT, "token.json"),
)
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "")


def _get_google_creds():
    """Authenticate with Google via OAuth2 Desktop flow (used for Gmail only)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, _GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}. "
                    "Download it from the GCP Console (needed for Gmail only)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, _GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def _get_gmail_service():
    """Return an authenticated Gmail API service."""
    from googleapiclient.discovery import build

    creds = _get_google_creds()
    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Google Sheets Helpers (public sheet — no credentials required)
# ---------------------------------------------------------------------------
def _read_sheet_tab(tab_name: str) -> list[dict]:
    """Read all rows from a public Google Sheet tab via CSV export URL.

    The sheet must be shared as "Anyone with the link can view".
    The first row is treated as column headers.
    """
    if not GOOGLE_SHEETS_ID:
        raise ConnectionError("GOOGLE_SHEETS_ID not configured.")

    url = (
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab_name)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "BPO-MCP-Server/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    return [dict(row) for row in reader]


# ---------------------------------------------------------------------------
# PII Redaction Middleware
# ---------------------------------------------------------------------------
_PII_PATTERNS: list[tuple[str, str]] = [
    # Email addresses
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]"),
    # Phone numbers (international and local formats)
    (r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}", "[PHONE_REDACTED]"),
    # SSN / national ID patterns (XXX-XX-XXXX)
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    # Credit card numbers (basic pattern)
    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CC_REDACTED]"),
]


def redact_pii(text: str) -> str:
    """Apply regex-based PII redaction to the given text.

    Redacts emails, phone numbers, SSNs, and credit card numbers.
    This is a placeholder implementation — production systems should use
    a dedicated NER-based PII detection service.
    """
    redacted = text
    for pattern, replacement in _PII_PATTERNS:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


# ---------------------------------------------------------------------------
# Data Models (MCP-local, not shared with backend)
# ---------------------------------------------------------------------------
class TranscriptEntry(BaseModel):
    """A single PII-redacted call transcript."""
    transcript_id: str = Field(description="Unique transcript identifier")
    queue_id: str = Field(description="Queue the call was routed to")
    agent_id: str = Field(description="Agent who handled the call")
    content: str = Field(description="PII-redacted transcript text")
    duration_seconds: int = Field(description="Call duration")
    timestamp: str = Field(description="ISO 8601 timestamp of the call")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class AgentLeaveEntry(BaseModel):
    """A single agent leave record."""
    agent_id: str = Field(description="Agent identifier")
    agent_name: str = Field(description="Agent display name")
    leave_type: str = Field(description="'annual' or 'sick'")
    start_date: str = Field(description="Leave start date (YYYY-MM-DD)")
    end_date: str = Field(description="Leave end date (YYYY-MM-DD)")
    remaining_balance_days: float = Field(description="Remaining leave days for the year")
    status: str = Field(description="'approved' | 'pending' | 'rejected'")


class AgentMetricsEntry(BaseModel):
    """Performance metrics for a single agent."""
    agent_id: str = Field(description="Agent identifier")
    agent_name: str = Field(description="Agent display name")
    avg_handle_time_seconds: float = Field(description="Average handle time in seconds")
    csat_score: float = Field(description="Customer satisfaction score (0-5)")
    fcr_rate: float = Field(description="First-call resolution rate (0-1)")
    escalation_rate: float = Field(description="Escalation rate (0-1)")
    schedule_adherence: float = Field(description="Schedule adherence rate (0-1)")
    strengths: list[str] = Field(default_factory=list, description="Agent strengths")
    gaps: list[str] = Field(default_factory=list, description="Agent skill gaps")


class HistoricalDemandEntry(BaseModel):
    """A single record of historical call demand."""
    date: str = Field(description="Date of the record (YYYY-MM-DD)")
    queue_id: str = Field(description="Queue identifier")
    time_slot: str = Field(description="morning, afternoon, or evening")
    call_volume: int = Field(description="Number of calls received")
    avg_handle_time: int = Field(description="Average handle time in seconds")
    service_level: float = Field(description="Service level percentage (0-100)")


class CourseCatalogEntry(BaseModel):
    """A single training course record."""
    course_id: str = Field(description="Course identifier")
    course_name: str = Field(description="Name of the course")
    duration_hours: float = Field(description="Duration in hours")
    target_skill_gap: str = Field(description="Skill gap this course addresses (e.g. empathy)")


class AgentAvailabilityEntry(BaseModel):
    """Agent availability constraints."""
    agent_id: str = Field(description="Agent identifier")
    max_weekly_hours: float = Field(description="Maximum allowed weekly hours")
    current_scheduled_hours: float = Field(description="Currently assigned hours this week")
    preferred_shift: str = Field(description="morning, afternoon, or evening")


class WeeklyScheduleEntry(BaseModel):
    """A single scheduled shift record."""
    agent_id: str = Field(description="Agent identifier")
    shift_date: str = Field(description="Date of the shift (YYYY-MM-DD)")
    start_time: str = Field(description="Start time (HH:MM)")
    end_time: str = Field(description="End time (HH:MM)")


# ---------------------------------------------------------------------------
# Mock Data Generators (fallback when Google Sheets is unavailable)
# ---------------------------------------------------------------------------
def _generate_mock_transcripts(queue_id: str, time_window: str) -> list[dict]:
    """Generate mock transcript data for development.

    In production, this data comes from the Google Sheet.
    """
    raw_transcripts = [
        {
            "transcript_id": "TRX-001",
            "fcr_rate": 0.75,
            "escalation_rate": 0.08,
            "schedule_adherence": 0.90,
            "strengths": ["Efficiency"],
            "gaps": ["De-escalation"],
        },
    ]


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def get_transcripts(
    queue_id: str,
    time_window: str,
    limit: int = 50,
) -> list[dict]:
    """Fetch PII-redacted call transcripts from Google Sheets for a given queue and time window.

    Reads from the 'Transcripts' tab in the configured Google Sheet.
    Falls back to mock data if Google Sheets is unavailable.

    Args:
        queue_id: The queue identifier to fetch transcripts for.
        time_window: Time period in ISO week format (e.g. '2025-W24').
        limit: Maximum number of transcripts to return.

    Returns:
        A list of PII-redacted transcript records.
    """
    try:
        sheet_rows = _read_sheet_tab("Transcripts")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                # Filter by queue_id if the sheet has data for multiple queues
                if row.get("queue_id", "") and row["queue_id"] != queue_id:
                    continue
                raw_data.append({
                    "transcript_id": row.get("transcript_id", ""),
                    "queue_id": row.get("queue_id", queue_id),
                    "agent_id": row.get("agent_id", ""),
                    "content": row.get("content", ""),
                    "duration_seconds": int(row.get("duration_seconds", 0)),
                    "timestamp": row.get("timestamp", ""),
                    "metadata": {
                        "channel": row.get("channel", "phone"),
                        "sentiment": row.get("sentiment", "neutral"),
                    },
                })
        else:
            raise ValueError("No transcript data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets read failed ({e}).")
        raise

    # Apply PII redaction middleware
    redacted_transcripts: list[dict] = []
    for transcript in raw_data[:limit]:
        redacted = transcript.copy()
        redacted["content"] = redact_pii(redacted["content"])
        # Validate against schema
        entry = TranscriptEntry(**redacted)
        redacted_transcripts.append(entry.model_dump())

    print(f"[INFO] Returned {len(redacted_transcripts)} transcripts (source={source})")
    return redacted_transcripts


@mcp.tool()
def get_agent_leave_data(
    queue_id: str,
    time_window: str,
) -> list[dict]:
    """Fetch agent leave and absence records from Google Sheets.

    Reads from the 'Leave' tab in the configured Google Sheet.
    Falls back to mock data if Google Sheets is unavailable.

    Args:
        queue_id: The queue identifier to fetch leave data for.
        time_window: Time period in ISO week format (e.g. '2025-W24').

    Returns:
        A list of agent leave records with balances and dates.
    """
    try:
        sheet_rows = _read_sheet_tab("Leave")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                try:
                    balance = float(row.get("remaining_balance_days", 0))
                except (ValueError, TypeError):
                    balance = 0.0

                raw_data.append({
                    "agent_id": row.get("agent_id", ""),
                    "agent_name": row.get("agent_name", ""),
                    "leave_type": row.get("leave_type", "annual"),
                    "start_date": row.get("start_date", ""),
                    "end_date": row.get("end_date", ""),
                    "remaining_balance_days": balance,
                    "status": row.get("status", "pending"),
                })
        else:
            raise ValueError("No leave data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets leave read failed ({e}).")
        raise

    # Validate against schema
    validated: list[dict] = []
    for record in raw_data:
        entry = AgentLeaveEntry(**record)
        validated.append(entry.model_dump())

    print(f"[INFO] Returned {len(validated)} leave records (source={source})")
    return validated


@mcp.tool()
def get_agent_performance_data(
    queue_id: str,
) -> list[dict]:
    """Fetch agent performance metrics from Google Sheets.

    Reads from the 'AgentMetrics' tab in the configured Google Sheet.
    Falls back to mock data if Google Sheets is unavailable.

    Args:
        queue_id: The queue identifier to fetch metrics for.

    Returns:
        A list of agent performance records with KPIs.
    """
    try:
        sheet_rows = _read_sheet_tab("AgentMetrics")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                # Parse comma-separated strengths/gaps into lists
                strengths_raw = row.get("strengths", "")
                gaps_raw = row.get("gaps", "")
                strengths = [s.strip() for s in strengths_raw.split(",") if s.strip()] if strengths_raw else []
                gaps = [g.strip() for g in gaps_raw.split(",") if g.strip()] if gaps_raw else []

                raw_data.append({
                    "agent_id": row.get("agent_id", ""),
                    "agent_name": row.get("agent_name", ""),
                    "avg_handle_time_seconds": float(row.get("avg_handle_time_seconds", 0)),
                    "csat_score": float(row.get("csat_score", 0)),
                    "fcr_rate": float(row.get("fcr_rate", 0)),
                    "escalation_rate": float(row.get("escalation_rate", 0)),
                    "schedule_adherence": float(row.get("schedule_adherence", 0)),
                    "strengths": strengths,
                    "gaps": gaps,
                })
        else:
            raise ValueError("No agent performance data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets metrics read failed ({e}).")
        raise

    # Validate against schema
    validated: list[dict] = []
    for record in raw_data:
        entry = AgentMetricsEntry(**record)
        validated.append(entry.model_dump())

    print(f"[INFO] Returned {len(validated)} agent metrics (source={source})")
    return validated


@mcp.tool()
def get_historical_demand(
    queue_id: str,
    time_window: str,
) -> list[dict]:
    """Fetch historical demand data from Google Sheets for forecasting.

    Reads from the 'HistoricalDemand' tab in the configured Google Sheet.
    Falls back to an empty list or error if unavailable.

    Args:
        queue_id: The queue identifier to fetch demand for.
        time_window: Time period in ISO week format (e.g. '2025-W24').

    Returns:
        A list of historical demand records (volumes and KPIs).
    """
    try:
        sheet_rows = _read_sheet_tab("HistoricalDemand")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                if row.get("queue_id", "") and row["queue_id"] != queue_id:
                    continue
                
                try:
                    vol = int(row.get("call_volume", 0))
                    aht = int(row.get("avg_handle_time", 0))
                    sl = float(row.get("service_level", 0))
                except (ValueError, TypeError):
                    vol, aht, sl = 0, 0, 0.0

                raw_data.append({
                    "date": row.get("date", ""),
                    "queue_id": row.get("queue_id", queue_id),
                    "time_slot": row.get("time_slot", "morning"),
                    "call_volume": vol,
                    "avg_handle_time": aht,
                    "service_level": sl,
                })
        else:
            raise ValueError("No historical demand data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets historical demand read failed ({e}).")
        raise

    # Validate against schema
    validated: list[dict] = []
    for record in raw_data:
        entry = HistoricalDemandEntry(**record)
        validated.append(entry.model_dump())

    print(f"[INFO] Returned {len(validated)} historical demand records (source={source})")
    return validated


@mcp.tool()
def get_course_catalog() -> list[dict]:
    """Fetch the corporate training course catalog.

    Reads from the 'CourseCatalog' tab in the configured Google Sheet.

    Returns:
        A list of available training courses.
    """
    try:
        sheet_rows = _read_sheet_tab("CourseCatalog")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                try:
                    duration = float(row.get("duration_hours", 0))
                except (ValueError, TypeError):
                    duration = 0.0

                raw_data.append({
                    "course_id": row.get("course_id", ""),
                    "course_name": row.get("course_name", ""),
                    "duration_hours": duration,
                    "target_skill_gap": row.get("target_skill_gap", ""),
                })
        else:
            raise ValueError("No course catalog data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets course catalog read failed ({e}).")
        raise

    validated: list[dict] = []
    for record in raw_data:
        entry = CourseCatalogEntry(**record)
        validated.append(entry.model_dump())

    print(f"[INFO] Returned {len(validated)} courses (source={source})")
    return validated


@mcp.tool()
def get_agent_availability() -> list[dict]:
    """Fetch maximum hours and shift preferences for agents.

    Reads from the 'AgentAvailability' tab in the configured Google Sheet.

    Returns:
        A list of agent availability constraints.
    """
    try:
        sheet_rows = _read_sheet_tab("AgentAvailability")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                try:
                    mwh = float(row.get("max_weekly_hours", 0))
                    csh = float(row.get("current_scheduled_hours", 0))
                except (ValueError, TypeError):
                    mwh, csh = 40.0, 0.0

                raw_data.append({
                    "agent_id": row.get("agent_id", ""),
                    "max_weekly_hours": mwh,
                    "current_scheduled_hours": csh,
                    "preferred_shift": row.get("preferred_shift", "morning"),
                })
        else:
            raise ValueError("No agent availability data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets agent availability read failed ({e}).")
        raise

    validated: list[dict] = []
    for record in raw_data:
        entry = AgentAvailabilityEntry(**record)
        validated.append(entry.model_dump())

    print(f"[INFO] Returned {len(validated)} availability records (source={source})")
    return validated


@mcp.tool()
def get_weekly_schedules(agent_ids: list[str]) -> list[dict]:
    """Fetch weekly shift schedules for specific agents to evaluate swap feasibility.

    Reads from the 'WeeklySchedules' tab in the configured Google Sheet.

    Args:
        agent_ids: List of agent IDs (e.g. ['AGT-201', 'AGT-202']) to fetch schedules for.

    Returns:
        A list of scheduled shifts strictly for the requested agents.
    """
    try:
        sheet_rows = _read_sheet_tab("WeeklySchedules")
        if sheet_rows:
            source = "google_sheets"
            raw_data = []
            for row in sheet_rows:
                ag_id = row.get("agent_id", "")
                if ag_id in agent_ids:
                    raw_data.append({
                        "agent_id": ag_id,
                        "shift_date": row.get("shift_date", ""),
                        "start_time": row.get("start_time", ""),
                        "end_time": row.get("end_time", ""),
                    })
        else:
            raise ValueError("No weekly schedules data found in Google Sheets")
    except Exception as e:
        print(f"[ERROR] Google Sheets weekly schedules read failed ({e}).")
        raise

    validated: list[dict] = []
    for record in raw_data:
        entry = WeeklyScheduleEntry(**record)
        validated.append(entry.model_dump())

    print(f"[INFO] Returned {len(validated)} schedule records for agents {agent_ids} (source={source})")
    return validated


@mcp.tool()
def send_results_email(
    to_email: str,
    subject: str,
    body_html: str,
    run_id: str,
) -> dict:
    """Send an HTML email with flow results via the Gmail API.

    Uses the authenticated user's Gmail account to send the email.
    This is used to notify managers of completed flow results.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body_html: HTML body content of the email.
        run_id: The flow run ID (for tracking/logging).

    Returns:
        A dict with send status and message ID.
    """
    try:
        service = _get_gmail_service()

        message = MIMEMultipart("alternative")
        message["to"] = to_email
        message["subject"] = subject
        message.attach(MIMEText(body_html, "html"))

        # Encode the message for the Gmail API
        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("utf-8")

        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )

        print(f"[INFO] Email sent to {to_email} for run {run_id} (message_id={sent['id']})")
        return {
            "status": "sent",
            "message_id": sent["id"],
            "to_email": to_email,
            "run_id": run_id,
        }

    except Exception as e:
        print(f"[ERROR] Failed to send email to {to_email}: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "to_email": to_email,
            "run_id": run_id,
        }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
