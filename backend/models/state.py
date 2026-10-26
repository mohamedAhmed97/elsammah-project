"""
BPO Ops Superflow — Shared State & Data Models

All Pydantic models that cross boundaries between agents, the API,
and the frontend. This is the single source of truth for types.
"""

from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Type Aliases
# ---------------------------------------------------------------------------
FlowType = Literal["training", "schedule", "hybrid", "leave_review", "shift_swap"]
HITLStatus = Literal["not_required", "pending", "approved", "rejected", "edited"]


# ---------------------------------------------------------------------------
# Agent Performance Models
# ---------------------------------------------------------------------------
class AgentPerf(BaseModel):
    """Performance metrics for a single call center agent."""
    agent_id: str
    agent_name: str
    avg_handle_time_seconds: float
    csat_score: float = Field(ge=0, le=5)
    fcr_rate: float = Field(ge=0, le=1)
    escalation_rate: float = Field(ge=0, le=1)
    schedule_adherence: float = Field(ge=0, le=1)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class TeamPerfMetrics(BaseModel):
    """Aggregated team performance metrics."""
    agents: list[AgentPerf]
    team_avg_handle_time: float
    team_avg_csat: float
    team_avg_fcr: float
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Demand Forecast Models
# ---------------------------------------------------------------------------
class TimeSlot(BaseModel):
    """A single time slot in the demand forecast."""
    start_time: str  # ISO 8601
    end_time: str  # ISO 8601
    predicted_volume: int
    required_agents: int


class DemandForecast(BaseModel):
    """Predicted call volume and staffing requirements."""
    forecast_period: str
    slots: list[TimeSlot]
    total_predicted_volume: int


# ---------------------------------------------------------------------------
# Leave Analysis Models
# ---------------------------------------------------------------------------
class AgentLeave(BaseModel):
    """A single agent's leave record."""
    agent_id: str
    agent_name: str
    leave_type: Literal["annual", "sick"]
    start_date: date
    end_date: date
    remaining_balance_days: float
    status: Literal["approved", "pending", "rejected"]


class LeaveOverlap(BaseModel):
    """Detected overlap between two agents' leave periods."""
    agent_a_id: str
    agent_b_id: str
    overlap_start: date
    overlap_end: date
    affected_queue: str
    severity: Literal["low", "medium", "critical"]


class CoverageGap(BaseModel):
    """A day where agent coverage falls below requirements."""
    date: date
    queue_id: str
    available_agents: int
    required_agents: int
    gap_severity: Literal["low", "medium", "critical"]


class LeaveReport(BaseModel):
    """Complete leave analysis output."""
    report_period: str
    agent_leaves: list[AgentLeave]
    overlaps: list[LeaveOverlap]
    coverage_gaps: list[CoverageGap]


# ---------------------------------------------------------------------------
# Schedule Models
# ---------------------------------------------------------------------------
class ShiftAssignment(BaseModel):
    """A single shift assignment for an agent."""
    agent_id: str
    shift_start: str  # ISO 8601
    shift_end: str  # ISO 8601
    assigned_queue: str
    reason: str


class ScheduleOutput(BaseModel):
    """Generated shift schedule."""
    schedule_period: str
    assignments: list[ShiftAssignment]
    coverage_score: float = Field(ge=0, le=1)
    notes: str = ""


# ---------------------------------------------------------------------------
# Shift Swap Models
# ---------------------------------------------------------------------------
class SwapRequest(BaseModel):
    """A proposed shift swap between two agents."""
    agent_a_id: str
    agent_b_id: str
    shift_date: date
    shift_a_id: str
    shift_b_id: str
    reason: str


class ScheduleIntersection(BaseModel):
    """The computed intersection of two agents' schedules."""
    shared_shift_dates: list[date]
    shared_leave_dates: list[date]
    overlapping_availability_windows: list[TimeSlot]
    swap_compatible: bool


class ShiftSwapResult(BaseModel):
    """Result of a shift swap feasibility analysis."""
    feasible: bool
    agent_a_schedule_summary: str
    agent_b_schedule_summary: str
    intersection: ScheduleIntersection
    coverage_impact: str
    risk_flags: list[str] = Field(default_factory=list)
    recommendation: str


# ---------------------------------------------------------------------------
# Training Plan Models
# ---------------------------------------------------------------------------
class TrainingRecommendation(BaseModel):
    """A personalized training recommendation for one agent."""
    agent_id: str
    skill_gaps: list[str]
    recommended_modules: list[str]
    estimated_hours: float
    priority: Literal["low", "medium", "high", "critical"]


class TrainingPlan(BaseModel):
    """Generated training plan."""
    plan_period: str
    recommendations: list[TrainingRecommendation]
    priority_agents: list[str]


# ---------------------------------------------------------------------------
# Transcript Models
# ---------------------------------------------------------------------------
class RedactedTranscript(BaseModel):
    """A PII-redacted call transcript."""
    transcript_id: str
    queue_id: str
    agent_id: str
    content: str
    duration_seconds: int = 0
    timestamp: str = ""
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# HITL Models
# ---------------------------------------------------------------------------
class HITLDecision(BaseModel):
    """A manager's decision at the HITL checkpoint."""
    decision: Literal["approve", "reject", "edit"]
    reviewer_id: str
    comments: str
    edits: Optional[dict] = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Observability Models
# ---------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    """A timestamped entry in the flow audit log."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    step_name: str
    event_type: str  # "step_started", "step_completed", "error", "hitl", etc.
    message: str
    data: Optional[dict] = None


class ErrorDetail(BaseModel):
    """Typed error information — no generic catch-all."""
    step_name: str
    error_type: str  # "ValidationError", "MCPConnectionError", etc.
    message: str
    recoverable: bool


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------
class FlowStartRequest(BaseModel):
    """Request body for POST /api/flow/start."""
    flow_type: FlowType
    queue_id: str
    time_window: str  # e.g. "2025-W24"
    swap_request: Optional[SwapRequest] = None


class FlowStartResponse(BaseModel):
    """Response body for POST /api/flow/start."""
    run_id: str
    status: str = "started"


class HITLDecisionRequest(BaseModel):
    """Request body for POST /api/flow/{run_id}/hitl."""
    decision: Literal["approve", "reject", "edit"]
    reviewer_id: str
    comments: str
    edits: Optional[dict] = None


class HITLDecisionResponse(BaseModel):
    """Response body for POST /api/flow/{run_id}/hitl."""
    status: str  # "accepted"
    run_id: str


class APIError(BaseModel):
    """Typed error response — no unstructured error strings."""
    error_type: str  # e.g. "ValidationError", "FlowNotFoundError"
    message: str
    details: Optional[dict] = None


# ---------------------------------------------------------------------------
# Flow State — Single Source of Truth
# ---------------------------------------------------------------------------
class BPOFlowState(BaseModel):
    """The shared state object that flows through all pipeline agents.

    This is the single source of truth for the entire flow execution.
    """
    # ── Run Identity ──
    run_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Input Parameters ──
    flow_type: FlowType = "hybrid"
    time_window: str = ""
    queue_id: str = ""
    swap_request: Optional[SwapRequest] = None

    # ── Pipeline Data ──
    transcripts: list[RedactedTranscript] = Field(default_factory=list)
    team_perf: Optional[TeamPerfMetrics] = None
    demand_forecast: Optional[DemandForecast] = None
    leave_report: Optional[LeaveReport] = None
    schedule_output: Optional[ScheduleOutput] = None
    training_plan: Optional[TrainingPlan] = None
    swap_result: Optional[ShiftSwapResult] = None

    # ── HITL State ──
    hitl_status: HITLStatus = "not_required"
    hitl_decision: Optional[HITLDecision] = None

    # ── Observability ──
    current_step: str = ""
    audit_log: list[AuditLogEntry] = Field(default_factory=list)
    error_state: Optional[ErrorDetail] = None
