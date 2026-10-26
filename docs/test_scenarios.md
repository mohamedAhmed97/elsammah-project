# BPO Ops Superflow — Test Scenarios Documentation

> **Version:** 1.0.0
> **Date:** 2026-02-25
> **Author:** QA Engineer (AI-Generated)
> **Status:** Complete

---

## Table of Contents

1. [Test Strategy Overview](#1-test-strategy-overview)
2. [Flow-Level Test Scenarios](#2-flow-level-test-scenarios)
   - 2.1 Training Flow
   - 2.2 Schedule Flow
   - 2.3 Hybrid Flow
   - 2.4 Leave Review Flow
   - 2.5 Shift Swap Flow
3. [Agent-Level Test Scenarios](#3-agent-level-test-scenarios)
4. [API Endpoint Test Scenarios](#4-api-endpoint-test-scenarios)
5. [HITL (Human-in-the-Loop) Test Scenarios](#5-hitl-test-scenarios)
6. [SSE Event Streaming Test Scenarios](#6-sse-event-streaming-test-scenarios)
7. [MCP Server Test Scenarios](#7-mcp-server-test-scenarios)
8. [Data Model Validation Test Scenarios](#8-data-model-validation-test-scenarios)
9. [Error Handling Test Scenarios](#9-error-handling-test-scenarios)
10. [Integration Test Scenarios](#10-integration-test-scenarios)
11. [Frontend UI Test Scenarios](#11-frontend-ui-test-scenarios)
12. [Database Persistence Test Scenarios](#12-database-persistence-test-scenarios)
13. [Security & Privacy Test Scenarios](#13-security--privacy-test-scenarios)
14. [Performance & Reliability Test Scenarios](#14-performance--reliability-test-scenarios)

---

## 1. Test Strategy Overview

### System Under Test

The BPO Ops Superflow is a multi-agent AI pipeline with:
- **5 flow types:** `training`, `schedule`, `hybrid`, `leave_review`, `shift_swap`
- **6 AI agents:** Transcript Analyzer, Demand Forecaster, Leave Analyzer, Perf-Aware Scheduler, Shift Swap Coordinator, Trainer Designer
- **3 services:** Backend (FastAPI + CrewAI), MCP Server (FastMCP), Frontend (React + Vite)
- **1 database:** PostgreSQL for flow run persistence

### Test Priority Matrix

| Priority | Area | Rationale |
|----------|------|-----------|
| **P0** | Flow routing & HITL | Core pipeline correctness and EU AI Act compliance |
| **P1** | Agent output validation | Pydantic schema compliance for all agents |
| **P1** | API contract | Request/response validation for all endpoints |
| **P2** | MCP integration | External data fetching and PII redaction |
| **P2** | Error handling | Graceful degradation and typed error responses |
| **P3** | Frontend UI | Form validation, SSE rendering, HITL modal |
| **P3** | Performance | Concurrent flows, SSE throughput |

---

## 2. Flow-Level Test Scenarios

### 2.1 Training Flow

**Pipeline:** Gatekeeper → Transcript Analysis → Training Design → HITL → Finalize

| ID | Scenario | Preconditions | Steps | Expected Result |
|----|----------|---------------|-------|-----------------|
| TF-001 | Happy path — training flow end-to-end | MCP server running, valid credentials | 1. POST `/api/flow/start` with `flow_type=training`, `queue_id=Q-100`, `time_window=2025-W24` | Flow starts, returns `run_id` |
| | | | 2. Subscribe to SSE at `/api/flow/{run_id}/stream` | Receive `step_started` for `input_gatekeeper` |
| | | | 3. Wait for pipeline to reach HITL | Receive `hitl_required` event with `pending_outputs: ["training_plan"]` |
| | | | 4. POST HITL approve decision | Receive `hitl_resolved` then `flow_completed` events |
| TF-002 | Training flow skips demand forecasting | Valid inputs | Start training flow, observe audit log | `forecast_demand` step has `event_type=step_skipped` |
| TF-003 | Training flow skips leave analysis | Valid inputs | Start training flow, observe audit log | `analyze_leave` step has `event_type=step_skipped` |
| TF-004 | Training plan output schema validation | Flow reaches training design | Inspect `state.training_plan` | Contains `plan_period`, `recommendations[]` (each with `agent_id`, `skill_gaps`, `recommended_modules`, `estimated_hours`, `priority`), `priority_agents[]` |
| TF-005 | Training flow with HITL rejection | Flow reaches HITL pending | Submit `decision=reject` | `hitl_status=rejected`, flow completes with rejection logged |
| TF-006 | Training flow with HITL edit | Flow reaches HITL pending | Submit `decision=edit` with edits payload | `hitl_status=edited`, edits captured in audit log |

---

### 2.2 Schedule Flow

**Pipeline:** Gatekeeper → Transcript Analysis → Demand Forecast → Leave Analysis → Schedule Generation → HITL → Finalize

| ID | Scenario | Preconditions | Steps | Expected Result |
|----|----------|---------------|-------|-----------------|
| SF-001 | Happy path — schedule flow end-to-end | MCP server running | 1. POST start with `flow_type=schedule` | Flow starts successfully |
| | | | 2. Wait for all pipeline steps | Steps execute in order: gatekeeper → transcripts → forecast → leave → schedule |
| | | | 3. Approve HITL | Flow completes with `hitl_status=approved` |
| SF-002 | Schedule respects leave constraints | Leave data with approved absences | Run schedule flow, inspect assignments | No agent is assigned a shift during their approved leave dates |
| SF-003 | Schedule output schema validation | Flow reaches scheduler | Inspect `state.schedule_output` | Contains `schedule_period`, `assignments[]` (each with `agent_id`, `shift_start`, `shift_end`, `assigned_queue`, `reason`), `coverage_score` (0-1), `notes` |
| SF-004 | Demand forecast feeds into scheduling | Forecast predicts high morning volume | Inspect schedule assignments | Morning slots have more agents assigned than evening |
| SF-005 | Coverage score meets target | Normal operation | Inspect `coverage_score` | Score is ≥ 0.90 as per agent goal |
| SF-006 | Leave overlap detection in schedule flow | Two agents with overlapping leaves | Run schedule flow | `leave_overlap_detected` SSE event emitted with correct severity |

---

### 2.3 Hybrid Flow

**Pipeline:** Gatekeeper → Transcript Analysis → Demand Forecast → Leave Analysis → Schedule + Training (both) → HITL → Finalize

| ID | Scenario | Preconditions | Steps | Expected Result |
|----|----------|---------------|-------|-----------------|
| HF-001 | Happy path — hybrid flow produces both outputs | MCP server running | Start hybrid flow, approve HITL | Both `schedule_output` and `training_plan` populated in state |
| HF-002 | Hybrid HITL shows all pending outputs | Flow reaches HITL | Inspect HITL event | `pending_outputs` includes both `schedule_output` and `training_plan` |
| HF-003 | Hybrid flow executes schedule then training sequentially | Valid inputs | Monitor SSE events during hybrid flow | `step_started(generate_schedule)` → `step_completed(generate_schedule)` → `step_started(design_training)` → `step_completed(design_training)` |
| HF-004 | Hybrid flow — reject affects both outputs | Flow reaches HITL | Submit reject | Neither schedule nor training is finalized; `hitl_status=rejected` |

---

### 2.4 Leave Review Flow

**Pipeline:** Gatekeeper → Leave Analysis → HITL → Finalize

| ID | Scenario | Preconditions | Steps | Expected Result |
|----|----------|---------------|-------|-----------------|
| LR-001 | Happy path — leave review end-to-end | Leave data available | Start with `flow_type=leave_review` | Leave report generated, HITL reached with `pending_outputs: ["leave_report"]` |
| LR-002 | Leave review skips transcript analysis | Valid inputs | Observe audit log | `analyze_transcripts` has `event_type=step_skipped` |
| LR-003 | Leave review skips demand forecasting | Valid inputs | Observe audit log | `forecast_demand` has `event_type=step_skipped` |
| LR-004 | Leave report contains overlap detection | Two agents with overlapping absences | Inspect `state.leave_report.overlaps` | Overlaps detected with correct `agent_a_id`, `agent_b_id`, `overlap_start`, `overlap_end`, `severity` |
| LR-005 | Coverage gap computation | Multiple agents on leave same day | Inspect `state.leave_report.coverage_gaps` | Gaps flagged for days where coverage < 85% with correct `gap_severity` |
| LR-006 | Leave overlap severity classification | Overlaps of 1, 2-3, and 4+ days | Inspect severity values | 1 day = `low`, 2-3 days = `medium`, 4+ days = `critical` |

---

### 2.5 Shift Swap Flow

**Pipeline:** Gatekeeper → Leave Analysis → Shift Swap Coordination → HITL → Finalize

| ID | Scenario | Preconditions | Steps | Expected Result |
|----|----------|---------------|-------|-----------------|
| SS-001 | Happy path — feasible swap | Neither agent on leave on swap date | Start with `flow_type=shift_swap` and valid `swap_request` | `swap_result.feasible=true`, positive recommendation |
| SS-002 | Infeasible swap — agent on leave | Agent A has approved leave on swap date | Start swap flow | `swap_result.feasible=false`, risk flags mention leave conflict |
| SS-003 | Swap request missing — validation error | `swap_request=null` with `flow_type=shift_swap` | Start shift_swap flow | `error_state` set with `ValidationError: swap_request is required` |
| SS-004 | Swap feasibility SSE event | Flow completes swap analysis | Monitor SSE stream | `swap_feasibility` event emitted with `feasible` and `risk_flags` |
| SS-005 | Schedule intersection computed | Both agents have schedules | Inspect `swap_result.intersection` | Contains `shared_shift_dates`, `shared_leave_dates`, `overlapping_availability_windows`, `swap_compatible` |
| SS-006 | Shift swap skips transcript analysis | Valid swap request | Observe audit log | `analyze_transcripts` has `event_type=step_skipped` |
| SS-007 | Shift swap skips demand forecasting | Valid swap request | Observe audit log | `forecast_demand` has `event_type=step_skipped` |
| SS-008 | SwapRequest schema validation | Invalid swap_request fields | Submit with missing `agent_a_id` | 422 error with field-level validation details |

---

## 3. Agent-Level Test Scenarios

### 3.1 Input Gatekeeper

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| AG-001 | Valid inputs for all 5 flow types | State initialized, `run_id` and `created_at` populated, first audit log entry written |
| AG-002 | Missing `queue_id` | `error_state` set: `ValidationError`, `queue_id is required`, `recoverable=false` |
| AG-003 | Missing `time_window` | `error_state` set: `ValidationError`, `time_window is required`, `recoverable=false` |
| AG-004 | `shift_swap` without `swap_request` | `error_state` set: `ValidationError`, `swap_request is required for shift_swap`, `recoverable=false` |
| AG-005 | Error state prevents downstream steps | Error set in gatekeeper | `analyze_transcripts` returns early without processing |

### 3.2 Transcript Analyzer

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| TA-001 | Fetches transcripts via MCP successfully | `state.transcripts` populated with `RedactedTranscript` objects |
| TA-002 | Fetches agent performance data via MCP | `state.team_perf` populated with `TeamPerfMetrics` |
| TA-003 | MCP unavailable — transcripts | `state.transcripts = []`, audit log records `data_fetched_error` |
| TA-004 | MCP unavailable — performance data | `state.team_perf` populated with empty agents list and zero averages |
| TA-005 | Team averages computed correctly | Averages match manual calculation from agent data |
| TA-006 | Pydantic `ValidationError` caught | `error_state` set with type `ValidationError`, `recoverable=false` |
| TA-007 | `ConnectionError` caught | `error_state` set with type `MCPConnectionError`, `recoverable=true` |

### 3.3 Demand Forecaster

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| DF-001 | Produces 3 time slots (morning, afternoon, evening) | `state.demand_forecast.slots` has 3 entries with correct time ranges |
| DF-002 | `total_predicted_volume` equals sum of slot volumes | Math check passes |
| DF-003 | `confidence_score` within [0, 1] | Pydantic validation passes |
| DF-004 | `forecast_period` set to `state.time_window` | Period matches input |
| DF-005 | LLM fails to return structured data | `ValueError` raised, flow handles gracefully |
| DF-006 | `ValidationError` on output | `error_state` set with `ValidationError` |

### 3.4 Leave Analyzer

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| LA-001 | Parses leave records from MCP data | `state.leave_report.agent_leaves` populated correctly |
| LA-002 | Date normalization handles multiple formats | `YYYY-MM-DD`, `MM/DD/YYYY`, `DD/MM/YYYY` all parsed correctly |
| LA-003 | Overlap detection — adjacent leaves, no overlap | No overlap entry created |
| LA-004 | Overlap detection — partial overlap | Overlap recorded with correct start/end dates |
| LA-005 | Coverage gap — all agents available | No coverage gaps flagged |
| LA-006 | Coverage gap — multiple agents absent | Gaps flagged with correct severity classification |
| LA-007 | MCP unavailable — falls back to mock data | Mock data used, audit log notes MCP unavailability |

### 3.5 Perf-Aware Scheduler

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| PS-001 | Output conforms to `ScheduleOutput` schema | All fields valid, assignments use real agent IDs |
| PS-002 | `schedule_period` set to `state.time_window` | Period matches input |
| PS-003 | Each assignment has a `reason` | No empty reason strings |
| PS-004 | LLM fails to return structured data | `ValueError` raised |
| PS-005 | Agent on leave not scheduled | No assignment for agent during leave dates |

### 3.6 Shift Swap Coordinator

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| SC-001 | Output conforms to `ShiftSwapResult` schema | All required fields present |
| SC-002 | Missing `swap_request` | `error_state` set with `ValidationError` |
| SC-003 | Intersection has all sub-fields | `shared_shift_dates`, `shared_leave_dates`, `overlapping_availability_windows`, `swap_compatible` all present |
| SC-004 | LLM fails to return structured data | `ValueError` raised |

### 3.7 Trainer Designer

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| TD-001 | Output conforms to `TrainingPlan` schema | All fields valid |
| TD-002 | `priority_agents` contains top 3 agent IDs | List has ≤ 3 entries from agent dataset |
| TD-003 | `plan_period` set to `state.time_window` | Period matches input |
| TD-004 | Priority classification is correct | `critical`, `high`, `medium`, `low` based on gap severity |
| TD-005 | LLM fails to return structured data | `ValueError` raised |

---

## 4. API Endpoint Test Scenarios

### 4.1 `POST /api/flow/start`

| ID | Scenario | Request | Expected |
|----|----------|---------|----------|
| API-001 | Valid training flow start | `{flow_type: "training", queue_id: "Q-100", time_window: "2025-W24"}` | 201, `{run_id: <uuid>, status: "started"}` |
| API-002 | Valid schedule flow start | `{flow_type: "schedule", queue_id: "Q-200", time_window: "2025-W24"}` | 201 |
| API-003 | Valid hybrid flow start | `{flow_type: "hybrid", ...}` | 201 |
| API-004 | Valid leave_review flow start | `{flow_type: "leave_review", ...}` | 201 |
| API-005 | Valid shift_swap flow start | `{flow_type: "shift_swap", ..., swap_request: {...}}` | 201 |
| API-006 | Invalid flow_type | `{flow_type: "invalid"}` | 422, `ValidationError` |
| API-007 | Missing required fields | `{}` | 422, `ValidationError` with field errors |
| API-008 | Empty queue_id | `{flow_type: "training", queue_id: "", time_window: "2025-W24"}` | Flow starts but gatekeeper sets error_state |

### 4.2 `POST /api/flow/{run_id}/hitl`

| ID | Scenario | Expected |
|----|----------|----------|
| API-009 | Approve pending flow | 200, `{status: "decision_accepted"}` |
| API-010 | Reject pending flow | 200, `{status: "decision_accepted"}` |
| API-011 | Edit pending flow with edits payload | 200, edits applied |
| API-012 | HITL on non-existent run_id | 404, `FlowNotFoundError` |
| API-013 | HITL on non-pending flow | 400, `InvalidStateTransition` |
| API-014 | Missing `reviewer_id` | 422, `ValidationError` |
| API-015 | Missing `comments` | 422, `ValidationError` |
| API-016 | Invalid `decision` value | 422, `ValidationError` |

### 4.3 `GET /api/flow/{run_id}/state`

| ID | Scenario | Expected |
|----|----------|----------|
| API-017 | Get state of active flow | 200, full `BPOFlowState` JSON |
| API-018 | Get state of non-existent run_id | 404, `FlowNotFoundError` |
| API-019 | State reflects current pipeline position | `current_step` matches the actively running agent |

### 4.4 `GET /api/flow/{run_id}/stream`

| ID | Scenario | Expected |
|----|----------|----------|
| API-020 | SSE stream opens successfully | EventSource connection established, events received |
| API-021 | Stream delivers events in order | Events arrive in chronological pipeline order |
| API-022 | Stream terminates on `flow_completed` | Connection closes after terminal event |
| API-023 | Stream terminates on `flow_error` | Connection closes after error event |
| API-024 | Stream for non-existent run_id | 404 error |

### 4.5 `GET /api/flow/history` & `GET /api/flow/history/{run_id}`

| ID | Scenario | Expected |
|----|----------|----------|
| API-025 | List flow history — empty DB | 200, empty array `[]` |
| API-026 | List flow history — multiple runs | 200, array of run summaries ordered by `created_at` desc, max 50 |
| API-027 | Get specific run history | 200, full `BPOFlowState` data |
| API-028 | Get non-existent run history | 404, `Run not found in history` |

### 4.6 `GET /health`

| ID | Scenario | Expected |
|----|----------|----------|
| API-029 | Health check | 200, `{status: "healthy", service: "bpo-ops-superflow-backend"}` |

---

## 5. HITL Test Scenarios

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| HITL-001 | Approve decision — state transitions | Submit approve | `hitl_status` transitions: `not_required` → `pending` → `approved` |
| HITL-002 | Reject decision — state transitions | Submit reject | `hitl_status` transitions: `not_required` → `pending` → `rejected` |
| HITL-003 | Edit decision — state transitions | Submit edit with edits | `hitl_status` transitions: `not_required` → `pending` → `edited` |
| HITL-004 | Decision logged in audit log | Any decision | Audit entry with `step_name=finalize`, `event_type=hitl_resolved`, `reviewer_id` and `comments` captured |
| HITL-005 | HITL pauses flow thread | Pipeline reaches checkpoint | `_hitl_event.wait()` blocks until `resume_after_hitl()` called |
| HITL-006 | SSE events emitted correctly | HITL lifecycle | `hitl_required` event on pause, `hitl_resolved` event on resume |
| HITL-007 | Multiple pending outputs in hybrid flow | Hybrid flow reaches HITL | `pending_outputs` includes both `schedule_output` and `training_plan` |
| HITL-008 | Flow saved to DB after HITL resolution | Complete any flow with HITL | `FlowRun` record persisted in PostgreSQL |
| HITL-009 | Email sent on approved/edited flow | `MANAGER_EMAIL` configured, flow approved | `send_results_email` MCP tool called, audit log records `email_sent` |
| HITL-010 | Email failure doesn't block finalization | Email send fails | Flow completes, audit log records `email_failed`, no crash |

---

## 6. SSE Event Streaming Test Scenarios

| ID | Scenario | Expected Events |
|----|----------|-----------------|
| SSE-001 | Training flow event sequence | `step_started(gatekeeper)` → `step_completed(gatekeeper)` → `step_started(analyze_transcripts)` → `step_completed(analyze_transcripts)` → `step_started(design_training)` → `step_completed(design_training)` → `hitl_required` → (pause) → `hitl_resolved` → `flow_completed` |
| SSE-002 | Leave overlap event | Leave analysis detects overlaps | `leave_overlap_detected` with `overlaps_count` and max `severity` |
| SSE-003 | Swap feasibility event | Shift swap completes | `swap_feasibility` with `feasible` boolean and `risk_flags` list |
| SSE-004 | Error event format | Agent fails | `flow_error` with `error_type` and `message` |
| SSE-005 | Event data envelope | Any event | Contains `run_id`, `timestamp` (ISO 8601), `step` |
| SSE-006 | Late SSE subscriber | Connect after some events emitted | Receives all events from beginning (events stored in-memory) |

---

## 7. MCP Server Test Scenarios

### 7.1 Tool: `get_transcripts`

| ID | Scenario | Expected |
|----|----------|----------|
| MCP-001 | Fetch transcripts from Google Sheets | List of `TranscriptEntry` dicts with PII-redacted `content` |
| MCP-002 | Filter by `queue_id` | Only transcripts matching the queue returned |
| MCP-003 | Limit parameter respected | At most `limit` transcripts returned |
| MCP-004 | Google Sheets unavailable | Exception raised (no silent fallback) |

### 7.2 Tool: `get_agent_leave_data`

| ID | Scenario | Expected |
|----|----------|----------|
| MCP-005 | Fetch leave data from Google Sheets | List of `AgentLeaveEntry` dicts |
| MCP-006 | Google Sheets unavailable | Exception raised |

### 7.3 Tool: `get_agent_performance_data`

| ID | Scenario | Expected |
|----|----------|----------|
| MCP-007 | Fetch metrics from Google Sheets | List of `AgentMetricsEntry` dicts |
| MCP-008 | Comma-separated strengths/gaps parsed | `strengths` and `gaps` are proper lists |
| MCP-009 | Numeric fields parsed correctly | `avg_handle_time_seconds`, scores, rates are correct floats |
| MCP-010 | Google Sheets unavailable | Exception raised |

### 7.4 Tool: `send_results_email`

| ID | Scenario | Expected |
|----|----------|----------|
| MCP-011 | Send email successfully | `{status: "sent", message_id: ...}` |
| MCP-012 | Email send fails | `{status: "failed", error: ...}` — no exception thrown |

### 7.5 PII Redaction

| ID | Scenario | Input | Expected Output |
|----|----------|-------|-----------------|
| PII-001 | Email redaction | `user@example.com` | `[EMAIL_REDACTED]` |
| PII-002 | Phone number redaction | `+1-555-123-4567` | `[PHONE_REDACTED]` |
| PII-003 | SSN redaction | `123-45-6789` | `[SSN_REDACTED]` |
| PII-004 | Credit card redaction | `4111-2222-3333-4444` | `[CC_REDACTED]` |
| PII-005 | Multiple PII in one text | Text with email + phone | Both redacted in single pass |
| PII-006 | No PII in text | Clean transcript | Text returned unchanged |

---

## 8. Data Model Validation Test Scenarios

| ID | Model | Scenario | Expected |
|----|-------|----------|----------|
| DM-001 | `AgentPerf` | `csat_score` > 5 | Pydantic `ValidationError` |
| DM-002 | `AgentPerf` | `fcr_rate` > 1 | Pydantic `ValidationError` |
| DM-003 | `AgentPerf` | `escalation_rate` < 0 | Pydantic `ValidationError` |
| DM-004 | `DemandForecast` | `confidence_score` > 1 | Pydantic `ValidationError` |
| DM-005 | `ScheduleOutput` | `coverage_score` < 0 | Pydantic `ValidationError` |
| DM-006 | `LeaveOverlap` | Invalid `severity` value | Pydantic `ValidationError` |
| DM-007 | `CoverageGap` | Invalid `gap_severity` | Pydantic `ValidationError` |
| DM-008 | `TrainingRecommendation` | Invalid `priority` | Pydantic `ValidationError` |
| DM-009 | `HITLDecision` | Invalid `decision` value | Pydantic `ValidationError` |
| DM-010 | `FlowStartRequest` | Invalid `flow_type` | Pydantic `ValidationError` |
| DM-011 | `BPOFlowState` | Default values populated | `hitl_status=not_required`, `flow_type=hybrid`, empty lists |

---

## 9. Error Handling Test Scenarios

| ID | Scenario | Error Type | Expected Behavior |
|----|----------|-----------|-------------------|
| ERR-001 | Invalid input at gatekeeper | `ValidationError` | `error_state` set, downstream steps skipped, `flow_error` SSE emitted |
| ERR-002 | MCP connection failure (transcripts) | `MCPConnectionError` | `error_state` set with `recoverable=true` |
| ERR-003 | MCP connection failure (leave data) | `MCPConnectionError` | `error_state` set with `recoverable=true` |
| ERR-004 | LLM returns invalid structure | `ValueError` | Raised within agent, caught at flow level |
| ERR-005 | Pydantic schema violation in agent output | `ValidationError` | `error_state` set with `recoverable=false` |
| ERR-006 | Router receives error state | — | Routes to `"error"` path, `handle_error()` emits `flow_error` |
| ERR-007 | Unhandled exception in flow thread | `Exception` | `error_state` set in `_run_flow_in_thread`, `flow_error` SSE emitted, flow marked completed |
| ERR-008 | Pydantic validation error at API layer | `ValidationError` | 422 response with `APIError` typed body |
| ERR-009 | Duplicate DB insert prevented | Same `run_id` saved twice | Second insert is no-op (checked before insert) |

---

## 10. Integration Test Scenarios

| ID | Scenario | Components | Expected |
|----|----------|-----------|----------|
| INT-001 | Backend ↔ MCP Server connectivity | Backend + MCP | MCP tools callable via `mcp_client.call_tool_sync()` |
| INT-002 | Backend ↔ PostgreSQL connectivity | Backend + DB | `FlowRun` records persist and are queryable |
| INT-003 | Frontend ↔ Backend API | Frontend + Backend | API calls succeed, CORS headers present |
| INT-004 | Frontend ↔ SSE stream | Frontend + Backend | `EventSource` connection opens, events render in LiveConsole |
| INT-005 | MCP ↔ Google Sheets | MCP + Google API | Data fetched from configured spreadsheet |
| INT-006 | MCP ↔ Gmail | MCP + Gmail API | Email sent to configured manager |
| INT-007 | Docker Compose — all services start | All containers | Backend, MCP, Frontend, DB all healthy |
| INT-008 | Backend starts with DB table creation | Backend + DB | `init_db.init_db()` creates `flow_runs` table |
| INT-009 | End-to-end: Start flow → SSE → HITL → DB persist | All | Full lifecycle completes, data persists |

---

## 11. Frontend UI Test Scenarios

### 11.1 RunForm Component

| ID | Scenario | Expected |
|----|----------|----------|
| UI-001 | Flow type selector shows all 5 options | Dropdown contains: training, schedule, hybrid, leave_review, shift_swap |
| UI-002 | Shift swap fields appear conditionally | Swap request fields shown only when `flow_type=shift_swap` |
| UI-003 | Required field validation | Submit without queue_id → validation error displayed |
| UI-004 | Successful submission | Form data sent to `/api/flow/start`, `run_id` received |

### 11.2 LiveConsole Component

| ID | Scenario | Expected |
|----|----------|----------|
| UI-005 | SSE events render in timeline | Each event displayed with timestamp, step name, and message |
| UI-006 | Terminal events close connection | `flow_completed` or `flow_error` stops SSE listener |
| UI-007 | Event ordering preserved | Events displayed in chronological order |

### 11.3 HITLModal Component

| ID | Scenario | Expected |
|----|----------|----------|
| UI-008 | Modal opens on `hitl_required` event | Modal appears with pending outputs listed |
| UI-009 | Approve button submits correct payload | `{decision: "approve", reviewer_id: ..., comments: ...}` |
| UI-010 | Reject button submits correct payload | `{decision: "reject", ...}` |
| UI-011 | Edit mode allows JSON edits | Edit textarea accepts JSON, submits as `edits` field |
| UI-012 | Comments field required | Cannot submit without entering comments |

### 11.4 ResultsPanel Component

| ID | Scenario | Expected |
|----|----------|----------|
| UI-013 | Schedule results display | Shift assignments rendered in table with all fields |
| UI-014 | Training plan results display | Recommendations listed with priority badges |
| UI-015 | Swap result display | Feasibility verdict, risk flags, recommendation shown |
| UI-016 | Leave report display | Agent leaves, overlaps, coverage gaps all rendered |

### 11.5 HistoryPanel Component

| ID | Scenario | Expected |
|----|----------|----------|
| UI-017 | History list loads from API | Past runs displayed with flow_type, status, created_at |
| UI-018 | Click run loads detail view | Full state JSON loaded and displayed |
| UI-019 | Empty history state | "No previous runs" message shown |

---

## 12. Database Persistence Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| DB-001 | Flow saved on natural completion (no HITL) | `FlowRun` with `status` matching `hitl_status` |
| DB-002 | Flow saved after HITL approval | `FlowRun` with `status=approved` |
| DB-003 | Flow saved after HITL rejection | `FlowRun` with `status=rejected` |
| DB-004 | Flow saved after HITL edit | `FlowRun` with `status=edited` |
| DB-005 | `results_data` contains full state dump | JSONB payload matches `BPOFlowState.model_dump()` |
| DB-006 | Duplicate prevention | Second save for same `run_id` is no-op |
| DB-007 | History endpoint reads from DB correctly | `/api/flow/history` returns persisted records |
| DB-008 | DB connection failure handled | `_save_flow_to_db` catches exception, prints error, doesn't crash |

---

## 13. Security & Privacy Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| SEC-001 | PII never reaches frontend | All transcript content passed through `redact_pii()` before leaving MCP |
| SEC-002 | CORS restricts origins | Only `localhost:5173` and `127.0.0.1:5173` allowed |
| SEC-003 | CORS preflight (OPTIONS) | Returns correct headers for cross-origin requests |
| SEC-004 | MCP server isolation | Frontend cannot directly access MCP server (port 8001 not exposed) |
| SEC-005 | HITL auditability | Every decision logs `reviewer_id`, `comments`, `decided_at` |
| SEC-006 | Credentials not in container image | `credentials.json` mounted as volume, not baked into Docker image |
| SEC-007 | API error responses use typed `APIError` | No raw exception strings leaked to clients |

---

## 14. Performance & Reliability Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| PERF-001 | Concurrent flow executions | Start 3+ flows simultaneously — each operates independently |
| PERF-002 | SSE memory management | Events stored per-flow in `_flow_registry` — no cross-contamination |
| PERF-003 | HITL timeout behavior | Flow waits indefinitely (no auto-approve) — emits warning after configurable timeout |
| PERF-004 | MCP client thread pool | `max_workers=5` — concurrent MCP calls don't deadlock |
| PERF-005 | DB session cleanup | `SessionLocal()` always closed in `finally` block |
| PERF-006 | Flow thread error recovery | Unhandled exception in flow thread is caught, error state set, flow marked completed |
| PERF-007 | Docker container restart policy | All services have `restart: unless-stopped` |
| PERF-008 | DB health check | PostgreSQL has `healthcheck` with retries; backend waits for healthy DB |

---

## Appendix A: Test Data Requirements

### Minimum Sample Data

| Data Type | Required Records | Source |
|-----------|-----------------|--------|
| Transcripts | 3+ per queue | Google Sheets "Transcripts" tab or `sample_data/Transcripts.csv` |
| Agent Metrics | 3+ agents | Google Sheets "AgentMetrics" tab or `sample_data/AgentMetrics.csv` |
| Leave Records | 3+ with overlaps | Google Sheets "Leave" tab or `sample_data/Leave.csv` |
| Swap Request | 1 valid pair | Inline in API request body |

### Test Environment

| Component | Configuration |
|-----------|--------------|
| Backend | `localhost:8000` |
| MCP Server | `localhost:8001` |
| Frontend | `localhost:5173` |
| PostgreSQL | `localhost:5432`, DB: `bpodb`, User: `bpo_user` |
| LLM Gateway | `LITELLM_API_KEY` and `LITELLM_BASE_URL` configured |
| Google Sheets | `GOOGLE_SHEETS_ID` configured with test data |

---

## Appendix B: Test Scenario Summary

| Category | Scenario Count |
|----------|---------------|
| Flow-Level (5 flows) | 30 |
| Agent-Level (7 agents) | 33 |
| API Endpoints | 29 |
| HITL Protocol | 10 |
| SSE Streaming | 6 |
| MCP Server | 12 |
| Data Model Validation | 11 |
| Error Handling | 9 |
| Integration | 9 |
| Frontend UI | 19 |
| Database Persistence | 8 |
| Security & Privacy | 7 |
| Performance & Reliability | 8 |
| **Total** | **191** |
