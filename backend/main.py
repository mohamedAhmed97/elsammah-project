import asyncio
import json
import uuid
import os
from datetime import datetime, timezone
from typing import Optional

# Force disable all CrewAI telemetry and LiteLLM tracing to prevent missing fastapi_sso/apscheduler dependency crashes
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["LITELLM_LOGGING"] = "false"

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from flow.bpo_flow import BPOSuperflow
from models.database import FlowRun, SessionLocal, engine
from models.state import (
    APIError,
    AuditLogEntry,
    BPOFlowState,
    FlowStartRequest,
    FlowStartResponse,
    HITLDecision,
    HITLDecisionRequest,
    HITLDecisionResponse,
)

# Initialize database tables
import init_db
init_db.init_db()

# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="BPO Ops Superflow API",
    description="Backend API for the BPO multi-agent optimization pipeline.",
    version="0.1.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-Memory Flow Registry
# ---------------------------------------------------------------------------
# Maps run_id -> (BPOSuperflow instance, list of SSE events, completed flag)
_flow_registry: dict[str, dict] = {}


def _get_flow_entry(run_id: str) -> dict:
    """Retrieve a flow entry or raise 404."""
    entry = _flow_registry.get(run_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIError(
                error_type="FlowNotFoundError",
                message=f"No flow found with run_id: {run_id}",
            ).model_dump(),
        )
    return entry


# ---------------------------------------------------------------------------
# SSE Event Broadcasting
# ---------------------------------------------------------------------------
def _create_sse_callback(run_id: str):
    """Create a callback that appends SSE events to the flow's event queue."""

    def callback(event_type: str, data: dict) -> None:
        entry = _flow_registry.get(run_id)
        if entry:
            entry["events"].append(
                {"event": event_type, "data": data}
            )

    return callback


def _run_flow_in_thread(run_id: str, flow: BPOSuperflow) -> None:
    """Run the flow and mark completion when done (including on error)."""
    try:
        flow.kickoff()
    except Exception as e:
        # Ensure errors are captured even if not caught by the flow
        if not flow.state.error_state:
            from models.state import ErrorDetail
            flow.state.error_state = ErrorDetail(
                step_name=flow.state.current_step or "unknown",
                error_type=type(e).__name__,
                message=str(e),
                recoverable=False,
            )
        # Emit error event
        flow._emit("flow_error", {
            "error_type": type(e).__name__,
            "message": str(e),
        })
    finally:
        entry = _flow_registry.get(run_id)
        if entry:
            entry["completed"] = True
            
        # If the flow completed naturally without HITL pause, save it now
        if flow.state.hitl_status in ("not_required", "approved", "rejected", "edited") or flow.state.error_state:
            _save_flow_to_db(run_id, flow)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.post(
    "/api/flow/start",
    response_model=FlowStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_flow(request: FlowStartRequest) -> FlowStartResponse:
    """Start a new BPO Ops Superflow pipeline run."""
    run_id = str(uuid.uuid4())

    # Initialize the flow
    flow = BPOSuperflow()
    flow.state.run_id = run_id
    flow.state.flow_type = request.flow_type
    flow.state.queue_id = request.queue_id
    flow.state.time_window = request.time_window
    flow.state.swap_request = request.swap_request
    flow.state.created_at = datetime.now(timezone.utc)

    # Register flow and set up SSE broadcasting
    _flow_registry[run_id] = {
        "flow": flow,
        "events": [],
        "completed": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    flow._sse_callback = _create_sse_callback(run_id)

    # Kick off the flow in a background thread
    asyncio.get_event_loop().run_in_executor(
        None, _run_flow_in_thread, run_id, flow
    )

    return FlowStartResponse(run_id=run_id, status="started")


@app.post("/api/flow/{run_id}/hitl")
async def handle_hitl_decision(run_id: str, decision: HITLDecisionRequest) -> HITLDecisionResponse:
    """Submit a manager's decision for a paused flow."""
    entry = _get_flow_entry(run_id)
    flow: BPOSuperflow = entry["flow"]

    if flow.state.hitl_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=APIError(
                error_type="InvalidStateTransition",
                message="Flow is not awaiting HITL approval.",
            ).model_dump(),
        )

    # Wrap the request payload
    decision_obj = HITLDecision(
        decision=decision.decision,
        reviewer_id=decision.reviewer_id,
        comments=decision.comments,
        edits=decision.edits,
    )

    # Resume the flow execution
    flow.resume_after_hitl(decision_obj)

    # Save to DB after a short delay to let finalize() update the status
    import threading
    def _delayed_save():
        import time
        time.sleep(3.0)  # Give finalize step time to complete
        _save_flow_to_db(run_id, flow)
    threading.Thread(target=_delayed_save, daemon=True).start()

    return HITLDecisionResponse(status="decision_accepted", run_id=run_id)


def _save_flow_to_db(run_id: str, flow: BPOSuperflow) -> None:
    """Persist the completed flow to PostgreSQL."""
    # Ensure it's in a terminal state
    if flow.state.hitl_status not in ("approved", "rejected", "edited", "not_required"):
        # Wait a moment for finalize step to complete and update status
        import time
        time.sleep(1.0)
        
    db = SessionLocal()
    try:
        # Check if already exists to prevent duplicate inserts
        if db.query(FlowRun).filter(FlowRun.run_id == run_id).first():
            return
            
        record = FlowRun(
            run_id=run_id,
            flow_type=flow.state.flow_type,
            queue_id=flow.state.queue_id,
            time_window=flow.state.time_window,
            status=flow.state.hitl_status,
            results_data=flow.state.model_dump(mode='json')
        )
        db.add(record)
        db.commit()
    except Exception as e:
        print(f"Failed to save flow {run_id} to DB: {e}")
    finally:
        db.close()


@app.get("/api/flow/history")
async def get_flow_history():
    """Retrieve metadata for all flow runs."""
    db = SessionLocal()
    try:
        runs = db.query(FlowRun).order_by(FlowRun.created_at.desc()).limit(50).all()
        return [
            {
                "run_id": r.run_id,
                "flow_type": r.flow_type,
                "queue_id": r.queue_id,
                "time_window": r.time_window,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]
    finally:
        db.close()


@app.get("/api/flow/history/{run_id}")
async def get_flow_history_detail(run_id: str):
    """Retrieve the full BPOFlowState payload for a past run."""
    db = SessionLocal()
    try:
        run = db.query(FlowRun).filter(FlowRun.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found in history.")
        return run.results_data
    finally:
        db.close()


@app.get("/api/flow/{run_id}/state")
async def get_flow_state(run_id: str) -> BPOFlowState:
    """Get the current snapshot of a flow's state."""
    entry = _get_flow_entry(run_id)
    flow: BPOSuperflow = entry["flow"]
    return flow.state


@app.get("/api/flow/{run_id}/stream")
async def stream_flow_events(run_id: str) -> EventSourceResponse:
    """Subscribe to real-time SSE events for a flow run."""
    entry = _get_flow_entry(run_id)

    async def event_generator():
        last_index = 0
        while True:
            events = entry["events"]
            if last_index < len(events):
                for event in events[last_index:]:
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"]),
                    }
                    # If we just sent a terminal event, stop
                    if event["event"] in ("flow_completed", "flow_error"):
                        return
                last_index = len(events)

            # If the flow thread has finished but no terminal event was emitted
            if entry.get("completed"):
                yield {
                    "event": "flow_completed",
                    "data": json.dumps({
                        "run_id": run_id,
                        "final_status": entry["flow"].state.hitl_status,
                    }),
                }
                return

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc: ValidationError):
    """Handle Pydantic validation errors with typed response."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=APIError(
            error_type="ValidationError",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "bpo-ops-superflow-backend"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
