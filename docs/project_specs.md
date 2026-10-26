# BPO Ops Superflow — Project Specification

> **Version:** 0.1.0 (Scaffold)
> **Date:** 2026-02-24
> **Status:** Draft

---

## 1. Overview

The **BPO Ops Superflow** is a unified multi-agent AI system that optimizes call center agent performance and workforce scheduling in a single pipeline. It is built on CrewAI Flows and integrates Human-in-the-Loop (HITL) checkpoints to comply with **EU AI Act** requirements for high-risk AI-assisted workforce decisions.

### 1.1 Objectives

| # | Objective |
|---|-----------|
| O1 | Analyze call transcripts to extract team performance metrics |
| O2 | Forecast demand based on historical call volume |
| O3 | Generate performance-aware shift schedules |
| O4 | Design targeted training plans for underperforming agents |
| O5 | Analyze annual/sick leave balances and detect coverage gaps from overlapping absences |
| O6 | Coordinate and validate shift swap requests between agents (schedule intersection check) |
| O7 | Require human manager approval before any schedule, swap, or training plan is finalized |
| O8 | Provide a real-time operations dashboard for visibility into AI pipeline state |

### 1.2 System Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                   BPO Ops Superflow                      │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────┐ │
│  │ Frontend  │◄─►│ Backend  │◄─►│ MCP Server           │ │
│  │ (React)   │   │ (FastAPI │   │ (FastMCP — Zendesk   │ │
│  │           │   │ + CrewAI)│   │   + PII Redaction)   │ │
│  └──────────┘   └──────────┘   └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Flow Types

The system supports five flow types, selected at run initiation:

| Flow Type | Pipeline Path | Output |
|-----------|--------------|--------|
| `training` | Gatekeeper → Transcript Analysis → Training Design → HITL → Finalize | `training_plan` |
| `schedule` | Gatekeeper → Transcript Analysis → Demand Forecast → Leave Analysis → Schedule Generation → HITL → Finalize | `schedule_output` |
| `hybrid` | Gatekeeper → Transcript Analysis → Demand Forecast → Leave Analysis → Schedule + Training (parallel) → HITL → Finalize | All outputs |
| `leave_review` | Gatekeeper → Leave Analysis → HITL → Finalize | `leave_report` |
| `shift_swap` | Gatekeeper → Leave Analysis → Shift Swap Coordination → HITL → Finalize | `swap_result` |

---

## 3. Agent Responsibilities

### 3.1 Input Gatekeeper

- **Role:** Flow initializer and input validator
- **Trigger:** `@start()` — entry point of every run
- **Responsibilities:**
  - Validate the incoming request (`flow_type`, `time_window`, `queue_id`)
  - Initialize the shared `BPOFlowState`
  - Write the first `audit_log` entry
- **Output:** Validated and initialized state

### 3.2 Transcript Analyzer

- **Role:** Performance data extractor
- **Trigger:** `@listen(input_gatekeeper)`
- **Responsibilities:**
  - Connect to FastMCP server to invoke `get_zendesk_transcripts` tool
  - Receive PII-redacted transcript data
  - Compute team performance metrics (avg handle time, CSAT, FCR, escalation rate)
  - Populate `state.team_perf`
- **Output:** `TeamPerfMetrics` object

### 3.3 Demand Forecaster

- **Role:** Call volume predictor
- **Trigger:** `@listen(analyze_transcripts)`
- **Responsibilities:**
  - Analyze historical call volume patterns
  - Generate staffing requirement predictions per time slot
  - Populate `state.demand_forecast`
- **Output:** `DemandForecast` object
- **Note:** Skipped in `training`-only flows

### 3.4 Perf-Aware Scheduler

- **Role:** Shift schedule optimizer
- **Trigger:** `@listen("schedule")` or `@listen("hybrid")`
- **Responsibilities:**
  - Combine `team_perf` metrics with `demand_forecast`
  - Generate optimized shift assignments that match agent strengths to demand peaks
  - Populate `state.schedule_output`
- **Output:** `ScheduleOutput` object

### 3.5 Trainer Designer

- **Role:** Training plan creator
- **Trigger:** `@listen("training")` or `@listen("hybrid")`
- **Responsibilities:**
  - Identify agents with below-threshold metrics
  - Generate personalized training recommendations
  - Populate `state.training_plan`
- **Output:** `TrainingPlan` object

### 3.6 Leave Analyzer

- **Role:** Leave balance inspector and coverage gap detector
- **Trigger:** `@listen(input_gatekeeper)` (for `leave_review` / `shift_swap` flows) or `@listen(analyze_transcripts)` (for `schedule` / `hybrid` flows)
- **Responsibilities:**
  - Fetch annual leave balances and sick leave history per agent
  - Detect **overlapping absences** — find date ranges where 2+ agents in the same queue are simultaneously on leave
  - Compute per-day coverage ratios and flag critical gaps (coverage < threshold)
  - For any two agents, compute their **schedule intersection** (shared shifts, shared leave days) to support swap feasibility
  - Populate `state.leave_report`
- **Output:** `LeaveReport` object

### 3.7 Shift Swap Coordinator

- **Role:** Swap request validator and impact analyzer
- **Trigger:** `@listen("shift_swap")`
- **Responsibilities:**
  - Accept a proposed swap between `agent_a` and `agent_b` for specific shift(s)
  - Use `leave_report` to verify neither agent is on leave during the swapped shift
  - Compute the **intersection** of both agents' schedules to confirm feasibility (overlapping availability windows)
  - Evaluate impact on queue coverage and team skill balance
  - Generate a `swap_result` with feasibility verdict, coverage impact, and risk flags
  - Populate `state.swap_result`
- **Output:** `ShiftSwapResult` object

### 3.8 Router

- **Role:** Conditional flow director and HITL gateway
- **Trigger:** `@router(forecast_demand)` / `@router(analyze_leave)` and HITL listener
- **Responsibilities:**
  - Route to `"training"`, `"schedule"`, `"hybrid"`, `"leave_review"`, or `"shift_swap"` path based on `flow_type`
  - At the HITL checkpoint: set `hitl_status = "pending"`, emit SSE event, and **pause** execution
  - Resume only after manager submits a decision via the HITL API endpoint
- **Output:** Routing signal or HITL decision

---

## 4. Shared State Schema

The `BPOFlowState` Pydantic model is the single source of truth across all agents:

```python
class BPOFlowState(BaseModel):
    # ── Run Identity ──
    run_id: str                           # UUID for this flow execution
    created_at: datetime                  # Timestamp of flow initiation

    # ── Input Parameters ──
    flow_type: FlowType                   # "training" | "schedule" | "hybrid" | "leave_review" | "shift_swap"
    time_window: str                      # e.g. "2025-W24"
    queue_id: str                         # Target queue identifier
    swap_request: Optional[SwapRequest]   # For shift_swap flows only

    # ── Pipeline Data ──
    transcripts: list[RedactedTranscript] # PII-cleaned transcript data
    team_perf: Optional[TeamPerfMetrics]  # Computed performance metrics
    demand_forecast: Optional[DemandForecast]  # Predicted call volumes
    leave_report: Optional[LeaveReport]        # Leave analysis + overlap detection
    schedule_output: Optional[ScheduleOutput]  # Generated shift schedule
    training_plan: Optional[TrainingPlan]      # Generated training plan
    swap_result: Optional[ShiftSwapResult]     # Swap feasibility + impact

    # ── HITL State ──
    hitl_status: HITLStatus               # "not_required" | "pending" | "approved" | "rejected" | "edited"
    hitl_decision: Optional[HITLDecision] # Manager's decision payload

    # ── Observability ──
    current_step: str                     # Name of the currently executing agent
    audit_log: list[AuditLogEntry]        # Timestamped log of all state transitions
    error_state: Optional[ErrorDetail]    # Typed error if pipeline fails
```

### 4.1 Nested Models

| Model | Key Fields |
|-------|-----------|
| `TeamPerfMetrics` | `agents: list[AgentPerf]`, `team_avg_handle_time`, `team_avg_csat`, `team_avg_fcr`, `computed_at` |
| `AgentPerf` | `agent_id`, `agent_name`, `avg_handle_time`, `csat_score`, `fcr_rate`, `escalation_rate`, `strengths`, `gaps` |
| `DemandForecast` | `forecast_period`, `slots: list[TimeSlot]`, `total_predicted_volume`, `confidence_score` |
| `TimeSlot` | `start_time`, `end_time`, `predicted_volume`, `required_agents` |
| `LeaveReport` | `report_period`, `agent_leaves: list[AgentLeave]`, `overlaps: list[LeaveOverlap]`, `coverage_gaps: list[CoverageGap]` |
| `AgentLeave` | `agent_id`, `leave_type: "annual" \| "sick"`, `start_date`, `end_date`, `remaining_balance_days`, `status` |
| `LeaveOverlap` | `agent_a_id`, `agent_b_id`, `overlap_start`, `overlap_end`, `affected_queue`, `severity: "low" \| "medium" \| "critical"` |
| `CoverageGap` | `date`, `queue_id`, `available_agents`, `required_agents`, `gap_severity` |
| `ScheduleOutput` | `schedule_period`, `assignments: list[ShiftAssignment]`, `coverage_score`, `notes` |
| `ShiftAssignment` | `agent_id`, `shift_start`, `shift_end`, `assigned_queue`, `reason` |
| `SwapRequest` | `agent_a_id`, `agent_b_id`, `shift_date`, `shift_a_id`, `shift_b_id`, `reason` |
| `ShiftSwapResult` | `feasible: bool`, `agent_a_schedule`, `agent_b_schedule`, `intersection: ScheduleIntersection`, `coverage_impact`, `risk_flags: list[str]`, `recommendation` |
| `ScheduleIntersection` | `shared_shift_dates: list[date]`, `shared_leave_dates: list[date]`, `overlapping_availability_windows: list[TimeSlot]`, `swap_compatible: bool` |
| `TrainingPlan` | `plan_period`, `recommendations: list[TrainingRecommendation]`, `priority_agents` |
| `TrainingRecommendation` | `agent_id`, `skill_gaps`, `recommended_modules`, `estimated_hours`, `priority` |
| `HITLDecision` | `decision: "approve" \| "reject" \| "edit"`, `reviewer_id`, `comments`, `edits: Optional[dict]`, `decided_at` |
| `AuditLogEntry` | `timestamp`, `step_name`, `event_type`, `message`, `data: Optional[dict]` |
| `ErrorDetail` | `step_name`, `error_type`, `message`, `recoverable` |
| `RedactedTranscript` | `transcript_id`, `queue_id`, `agent_id`, `content`, `metadata` |

---

## 5. HITL Protocol

### 5.1 EU AI Act Compliance Context

Under the EU AI Act (Article 14), AI systems used for workforce management decisions (scheduling, performance evaluation, training assignments) are classified as high-risk. Human oversight is mandatory before any AI-generated decision is applied.

### 5.2 Checkpoint Flow

```
Agent Pipeline Completes
        │
        ▼
  ┌─────────────┐
  │ HITL Pause   │  hitl_status = "pending"
  │ (SSE Event)  │──────► Frontend shows modal
  └─────────────┘
        │
        ▼ (waits for POST /api/flow/{run_id}/hitl)
        │
  ┌─────────────────────────────┐
  │ Manager Decision             │
  │  ├─ Approve → finalize as-is │
  │  ├─ Edit → apply edits, then │
  │  │         finalize           │
  │  └─ Reject → abort pipeline  │
  └─────────────────────────────┘
        │
        ▼
  ┌─────────────┐
  │ Finalize     │  Write audit log, mark complete
  └─────────────┘
```

### 5.3 HITL Contract

| Field | Type | Description |
|-------|------|-------------|
| `decision` | `Literal["approve", "reject", "edit"]` | Manager's verdict |
| `reviewer_id` | `str` | Authenticated manager identifier |
| `comments` | `str` | Free-text justification (required for audit) |
| `edits` | `Optional[dict]` | Partial override of `schedule_output` or `training_plan` |
| `decided_at` | `datetime` | Server-side timestamp |

---

## 6. API Contract Summary

| Method | Endpoint | Request Body | Response | Description |
|--------|----------|-------------|----------|-------------|
| `POST` | `/api/flow/start` | `FlowStartRequest` | `{ run_id: str }` | Initiate a new pipeline run |
| `GET` | `/api/flow/{run_id}/stream` | — | SSE stream | Real-time audit log & state events |
| `GET` | `/api/flow/{run_id}/state` | — | `BPOFlowState` | Current snapshot of flow state |
| `POST` | `/api/flow/{run_id}/hitl` | `HITLDecision` | `{ status: str }` | Submit manager decision |
| `POST` | `/api/flow/start` (swap) | `FlowStartRequest` with `swap_request` | `{ run_id: str }` | Initiate a shift swap analysis run |

### 6.1 SSE Event Types

| Event Type | Payload | Trigger |
|-----------|---------|---------|
| `step_started` | `{ step: str, timestamp: str }` | Agent begins execution |
| `step_completed` | `{ step: str, result_summary: str }` | Agent completes |
| `leave_overlap_detected` | `{ overlaps: list, severity: str }` | Leave analyzer found overlapping absences |
| `swap_feasibility` | `{ feasible: bool, risk_flags: list }` | Swap coordinator completed analysis |
| `hitl_required` | `{ run_id: str, pending_outputs: list }` | Pipeline paused for review |
| `hitl_resolved` | `{ decision: str, reviewer_id: str }` | Manager submitted decision |
| `flow_completed` | `{ run_id: str, final_status: str }` | Pipeline finished |
| `flow_error` | `{ step: str, error: ErrorDetail }` | Typed error occurred |

---

## 7. Error Handling Strategy

> **Constraint:** No generic `except Exception` catch-all blocks.

| Error Type | Scope | Handling |
|-----------|-------|----------|
| `ValidationError` | Input gatekeeper | Return 422 with field-level errors |
| `MCPConnectionError` | Transcript analyzer | Set `error_state`, emit `flow_error` SSE, mark step failed |
| `MCPToolError` | Transcript analyzer | Set `error_state` with tool-specific message |
| `AgentExecutionError` | Any agent step | Log to `audit_log`, set `error_state`, allow partial results |
| `HITLTimeoutError` | HITL checkpoint | After configurable timeout, emit warning SSE (do not auto-approve) |
| `SerializationError` | Any output step | Log malformed output, request agent retry once |

---

## 8. Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Orchestration | CrewAI Flows | ≥0.100.0 |
| Backend API | FastAPI + Uvicorn | Latest |
| MCP Server | FastMCP | ≥2.0 |
| Frontend | React + Vite + TypeScript | React 19, Vite 6 |
| Styling | Tailwind CSS | v4 |
| State Typing | Pydantic v2 | ≥2.0 |
| LLM Gateway | LiteLLM | Latest |
| Containerization | Docker + Docker Compose | Latest |

---

## 9. Security & Privacy

| Concern | Mitigation |
|---------|-----------|
| PII in transcripts | FastMCP applies regex-based PII redaction middleware before data leaves the MCP server |
| HITL auditability | All decisions logged with `reviewer_id`, `comments`, `decided_at` |
| Service isolation | MCP server runs as a separate container, unreachable from frontend |
| API access | CORS restricted to frontend origin; future: JWT auth layer |
