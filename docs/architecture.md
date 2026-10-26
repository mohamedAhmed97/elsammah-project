# BPO Ops Superflow — Architecture

> **Version:** 0.1.0 (Scaffold)
> **Date:** 2026-02-24

---

## 1. System Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend — React + Vite + Tailwind"]
        RF[RunForm]
        LC[LiveConsole]
        HM[HITLModal]
    end

    subgraph Backend["Backend — FastAPI + CrewAI"]
        API[FastAPI Server]
        SSE[SSE Broadcaster]
        BF[BPOSuperflow]

        subgraph Agents["CrewAI Flow Agents"]
            IG[InputGatekeeper]
            TA[TranscriptAnalyzer]
            DF[DemandForecaster]
            LA[LeaveAnalyzer]
            RT[Router]
            PS[PerfAwareScheduler]
            TD[TrainerDesigner]
            SSC[ShiftSwapCoordinator]
            HITL[HITL Checkpoint]
            FN[Finalizer]
        end
    end

    subgraph MCP["MCP Server — FastMCP"]
        ZT["get_zendesk_transcripts"]
        PII["PII Redaction Middleware"]
    end

    RF -->|POST /api/flow/start| API
    HM -->|POST /api/flow/:id/hitl| API
    SSE -->|SSE /api/flow/:id/stream| LC
    SSE -->|hitl_required event| HM

    API --> BF
    BF --> IG --> TA --> DF --> LA --> RT
    RT -->|schedule| PS
    RT -->|training| TD
    RT -->|hybrid| PS & TD
    RT -->|shift_swap| SSC
    RT -->|leave_review| HITL
    PS & TD & SSC --> HITL --> FN

    TA -->|MCP tool call| ZT
    ZT --> PII
    PII -->|redacted data| ZT

    style Frontend fill:#1e293b,stroke:#38bdf8,color:#e2e8f0
    style Backend fill:#1e293b,stroke:#a78bfa,color:#e2e8f0
    style MCP fill:#1e293b,stroke:#34d399,color:#e2e8f0
    style Agents fill:#0f172a,stroke:#a78bfa,color:#e2e8f0
```

---

## 2. Data Flow Sequence

```mermaid
sequenceDiagram
    actor Manager
    participant UI as React Frontend
    participant API as FastAPI Backend
    participant Flow as CrewAI BPOSuperflow
    participant MCP as FastMCP Server

    Manager->>UI: Select flow_type, queue_id, time_window
    UI->>API: POST /api/flow/start
    API->>Flow: kickoff(BPOFlowState)
    API-->>UI: { run_id }
    UI->>API: GET /api/flow/{run_id}/stream (SSE)

    Note over Flow: Step 1 — Input Gatekeeper
    Flow-->>API: audit_log: step_started
    API-->>UI: SSE: step_started

    Note over Flow: Step 2 — Transcript Analyzer
    Flow->>MCP: get_zendesk_transcripts(queue_id, time_window)
    MCP->>MCP: Apply PII redaction
    MCP-->>Flow: RedactedTranscript[]
    Flow-->>API: audit_log: step_completed (team_perf computed)
    API-->>UI: SSE: step_completed

    Note over Flow: Step 3 — Demand Forecaster
    Flow-->>API: audit_log: step_completed (forecast generated)
    API-->>UI: SSE: step_completed

    Note over Flow: Step 4 — Leave Analyzer
    Flow-->>Flow: Detect overlapping absences
    Flow-->>Flow: Compute schedule intersections
    Flow-->>API: audit_log: step_completed (leave_report generated)
    API-->>UI: SSE: leave_overlap_detected (if overlaps found)

    Note over Flow: Step 5 — Router → Scheduler / Trainer / Swap
    Flow-->>API: audit_log: step_completed
    API-->>UI: SSE: step_completed

    alt flow_type = shift_swap
        Note over Flow: Step 5a — Shift Swap Coordinator
        Flow-->>Flow: Validate swap feasibility
        Flow-->>Flow: Check intersection of agent schedules
        Flow-->>API: audit_log: swap analyzed
        API-->>UI: SSE: swap_feasibility
    end

    Note over Flow: Step 6 — HITL Checkpoint
    Flow-->>API: hitl_status = "pending"
    API-->>UI: SSE: hitl_required
    UI->>Manager: Show HITL Modal (schedule / training / swap / leave)

    Manager->>UI: Approve / Edit / Reject
    UI->>API: POST /api/flow/{run_id}/hitl
    API->>Flow: Resume with HITLDecision
    API-->>UI: SSE: hitl_resolved

    Note over Flow: Step 7 — Finalize
    Flow-->>API: audit_log: flow_completed
    API-->>UI: SSE: flow_completed
```

---

## 3. Directory Structure

```
crewai-bpo-challenge/
├── docs/
│   ├── project_specs.md          # This specification
│   ├── architecture.md           # This document
│   └── crewai_cheatsheet.md      # Existing reference
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                   # FastAPI app + SSE endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   └── state.py              # Pydantic models (BPOFlowState, etc.)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── transcript_analyzer.py
│   │   ├── demand_forecaster.py
│   │   ├── leave_analyzer.py
│   │   ├── perf_aware_scheduler.py
│   │   ├── shift_swap_coordinator.py
│   │   └── trainer_designer.py
│   └── flow/
│       ├── __init__.py
│       └── bpo_flow.py           # BPOSuperflow (CrewAI Flow class)
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── App.tsx               # Main layout
│       ├── main.tsx              # Entry point
│       ├── types.ts              # TypeScript interfaces
│       └── components/
│           ├── RunForm.tsx       # Flow initiation form
│           ├── LiveConsole.tsx   # SSE-powered audit timeline
│           └── HITLModal.tsx     # Approve / Edit / Reject modal
│
├── mcp_server/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py                 # FastMCP server + Zendesk tool + PII middleware
│
├── docker-compose.yml            # Orchestrates all 3 services
├── .env.example
├── .gitignore
├── mock_data/                    # Existing mock datasets
│   ├── tickets.json
│   ├── agent_metrics.json
│   └── campaigns.json
├── example_flow.py               # Existing reference (do not modify)
├── verify_setup.py               # Existing setup check
└── README.md
```

---

## 4. Service Communication

```mermaid
graph LR
    subgraph Ports
        F["Frontend :5173"]
        B["Backend :8000"]
        M["MCP Server :8001"]
    end

    F -->|HTTP/SSE| B
    B -->|MCP Protocol| M

    style F fill:#0f172a,stroke:#38bdf8,color:#e2e8f0
    style B fill:#0f172a,stroke:#a78bfa,color:#e2e8f0
    style M fill:#0f172a,stroke:#34d399,color:#e2e8f0
```

| Service | Port | Protocol | Upstream Dependency |
|---------|------|----------|-------------------|
| Frontend | 5173 | HTTP (Vite dev) | Backend |
| Backend | 8000 | HTTP + SSE | MCP Server |
| MCP Server | 8001 | MCP (stdio/SSE) | None (external Zendesk) |

---

## 5. API Endpoint Design

### 5.1 Flow Lifecycle

```
POST   /api/flow/start          → Start a new flow run
GET    /api/flow/{run_id}/state  → Get current state snapshot
GET    /api/flow/{run_id}/stream → Subscribe to SSE events
POST   /api/flow/{run_id}/hitl   → Submit HITL decision
```

### 5.2 Request / Response Models

#### `POST /api/flow/start`

```python
# Request
class FlowStartRequest(BaseModel):
    flow_type: Literal["training", "schedule", "hybrid", "leave_review", "shift_swap"]
    queue_id: str
    time_window: str  # e.g. "2025-W24"
    swap_request: Optional[SwapRequest] = None  # Required for shift_swap flows

# Response (201)
class FlowStartResponse(BaseModel):
    run_id: str
    status: str  # "started"
```

#### `POST /api/flow/{run_id}/hitl`

```python
# Request
class HITLDecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    reviewer_id: str
    comments: str
    edits: Optional[dict] = None

# Response (200)
class HITLDecisionResponse(BaseModel):
    status: str  # "accepted"
    run_id: str
```

### 5.3 Error Responses

All errors use a typed `APIError` model — no unstructured error strings:

```python
class APIError(BaseModel):
    error_type: str    # e.g. "ValidationError", "FlowNotFoundError"
    message: str
    details: Optional[dict] = None
```

| Status | Error Type | When |
|--------|-----------|------|
| 404 | `FlowNotFoundError` | `run_id` doesn't exist |
| 409 | `FlowStateConflictError` | HITL decision on non-pending flow |
| 422 | `ValidationError` | Invalid request body |
| 500 | `InternalPipelineError` | Unrecoverable agent failure |

---

## 6. HITL State Machine

```mermaid
stateDiagram-v2
    [*] --> not_required: Flow starts
    not_required --> pending: Pipeline outputs ready
    pending --> approved: Manager approves
    pending --> edited: Manager edits
    pending --> rejected: Manager rejects
    approved --> [*]: Finalize with original outputs
    edited --> [*]: Finalize with modified outputs
    rejected --> [*]: Abort — log rejection reason
```

---

## 7. SSE Event Schema

All SSE events conform to a unified envelope:

```typescript
interface SSEEvent {
  event: "step_started" | "step_completed" | "hitl_required"
       | "hitl_resolved" | "flow_completed" | "flow_error"
       | "leave_overlap_detected" | "swap_feasibility";
  data: {
    run_id: string;
    timestamp: string;     // ISO 8601
    step?: string;         // Agent step name
    message?: string;      // Human-readable description
    payload?: Record<string, unknown>;  // Event-specific data
  };
}
```

---

## 8. CrewAI Flow Graph

```mermaid
graph TD
    START["@start: input_gatekeeper"] --> TA["@listen: analyze_transcripts"]
    TA --> DF["@listen: forecast_demand"]
    DF --> LA["@listen: analyze_leave"]
    LA --> ROUTER{"@router: route_by_flow_type"}

    ROUTER -->|"schedule"| PS["@listen: generate_schedule"]
    ROUTER -->|"training"| TD["@listen: design_training"]
    ROUTER -->|"hybrid"| PS & TD
    ROUTER -->|"shift_swap"| SSC["@listen: coordinate_swap"]
    ROUTER -->|"leave_review"| HITL

    PS --> HITL["@listen: hitl_checkpoint"]
    TD --> HITL
    SSC --> HITL
    HITL --> FIN["@listen: finalize"]

    style START fill:#059669,stroke:#34d399,color:#fff
    style LA fill:#0d9488,stroke:#2dd4bf,color:#fff
    style ROUTER fill:#7c3aed,stroke:#a78bfa,color:#fff
    style SSC fill:#d97706,stroke:#fbbf24,color:#fff
    style HITL fill:#dc2626,stroke:#f87171,color:#fff
    style FIN fill:#0284c7,stroke:#38bdf8,color:#fff
```

Each node corresponds to a method on the `BPOSuperflow(Flow[BPOFlowState])` class. The HITL checkpoint is the **only** point where execution pauses for external input.

---

## 9. MCP Server Isolation

The MCP server is fully decoupled from backend logic:

| Concern | Implementation |
|---------|---------------|
| **No shared code** | Separate `requirements.txt`, separate Docker image |
| **No direct DB access** | Data sourced only from Zendesk API (or mock) |
| **PII never leaves MCP** | Redaction applied as middleware before tool returns |
| **Interface contract** | Tools: `get_zendesk_transcripts(queue_id, time_window) → list[RedactedTranscript]`, `get_agent_leave_data(queue_id, time_window) → list[AgentLeave]` |

The backend connects to the MCP server using the standard MCP client protocol. The MCP server knows nothing about CrewAI, schedules, or training plans.

---

## 10. Deployment Topology (Docker Compose)

```yaml
services:
  mcp_server:    # Port 8001, no external deps
  backend:       # Port 8000, depends_on: mcp_server
  frontend:      # Port 5173, depends_on: backend
```

All services share an `.env` file for API keys but are otherwise stateless. No persistent storage is needed for the scaffold phase.
