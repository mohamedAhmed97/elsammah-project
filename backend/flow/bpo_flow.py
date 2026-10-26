"""
BPO Ops Superflow — CrewAI Flow Class

The main orchestration flow that chains all agents together with
conditional routing and a HITL checkpoint for EU AI Act compliance.

Optimized flow graph (parallelized):
    input_gatekeeper → analyze_transcripts ─┬→ forecast_demand  ─┐
                                            └→ analyze_leave    ─┤→ sync → router
        → "schedule"    → generate_schedule       ─┐
        → "training"    → design_training          ├→ hitl_checkpoint → finalize
        → "hybrid"      → schedule ∥ training      ─┘
        → "shift_swap"  → coordinate_swap          ─┘
        → "leave_review" → hitl_checkpoint         ─┘
"""

import asyncio
import concurrent.futures
import threading
import uuid
from datetime import datetime, timezone

from crewai.flow.flow import Flow, listen, or_, and_, router, start
from pydantic import ValidationError

from agents.demand_forecaster import run_demand_forecast
from agents.leave_analyzer import run_leave_analysis
from agents.perf_aware_scheduler import run_schedule_generation
from agents.shift_swap_coordinator import run_shift_swap_coordination
from agents.trainer_designer import run_training_design
from agents.transcript_analyzer import run_transcript_analysis
from models.state import (
    AuditLogEntry,
    BPOFlowState,
    ErrorDetail,
    HITLDecision,
)


class BPOSuperflow(Flow[BPOFlowState]):
    """Main CrewAI Flow orchestrating the BPO Ops pipeline.

    Flow graph:
        input_gatekeeper → analyze_transcripts → run_parallel_post_transcript → route
                                                  ├ forecast_demand  (parallel)
                                                  └ analyze_leave    (parallel)
            → "schedule"    → generate_schedule  ─┐
            → "training"    → design_training     ├→ hitl_checkpoint → finalize
            → "hybrid"      → schedule + training ─┘
            → "shift_swap"  → coordinate_swap    ─┘
            → "leave_review" → hitl_checkpoint   ─┘
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ── HITL Synchronization ──
        # This event is set when a manager submits a decision via the API.
        # We use threading.Event because CrewAI flows run synchronously in a background thread.
        self._hitl_event = threading.Event()
        self._hitl_decision: HITLDecision | None = None

        # ── Parallel Step Synchronization ──
        # forecast_demand and analyze_leave run concurrently after analyze_transcripts.
        # This is now handled by asyncio.gather in run_parallel_post_transcript.

        # ── SSE Callback ──
        # Set by the API layer to broadcast events to connected clients.
        self._sse_callback = None

    def _emit(self, event_type: str, data: dict | None = None) -> None:
        """Emit an SSE event if a callback is registered."""
        if self._sse_callback and callable(self._sse_callback):
            self._sse_callback(
                event_type,
                {
                    "run_id": self.state.run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "step": self.state.current_step,
                    **(data or {}),
                },
            )

    # ── Step 1: Input Gatekeeper ──
    @start()
    def input_gatekeeper(self) -> None:
        """Validate inputs and initialize the flow state."""
        self.state.current_step = "input_gatekeeper"

        if not self.state.run_id:
            self.state.run_id = str(uuid.uuid4())
        if not self.state.created_at:
            self.state.created_at = datetime.now(timezone.utc)

        self.state.audit_log.append(
            AuditLogEntry(
                step_name="input_gatekeeper",
                event_type="step_started",
                message=(
                    f"Flow initialized: type={self.state.flow_type}, "
                    f"queue={self.state.queue_id}, window={self.state.time_window}"
                ),
            )
        )

        # Validate required fields
        if not self.state.queue_id:
            self.state.error_state = ErrorDetail(
                step_name="input_gatekeeper",
                error_type="ValidationError",
                message="queue_id is required.",
                recoverable=False,
            )
            return

        if not self.state.time_window:
            self.state.error_state = ErrorDetail(
                step_name="input_gatekeeper",
                error_type="ValidationError",
                message="time_window is required.",
                recoverable=False,
            )
            return

        if self.state.flow_type == "shift_swap" and not self.state.swap_request:
            self.state.error_state = ErrorDetail(
                step_name="input_gatekeeper",
                error_type="ValidationError",
                message="swap_request is required for shift_swap flow type.",
                recoverable=False,
            )
            return

        self._emit("step_started", {"step": "input_gatekeeper"})

        self.state.audit_log.append(
            AuditLogEntry(
                step_name="input_gatekeeper",
                event_type="step_completed",
                message="Input validation passed. State initialized.",
            )
        )
        self._emit("step_completed", {"step": "input_gatekeeper"})

    # ── Step 2: Transcript Analysis (must run first — populates team_perf) ──
    @listen(input_gatekeeper)
    def analyze_transcripts(self) -> None:
        """Invoke the TranscriptAnalyzer agent."""
        if self.state.error_state:
            return

        # Skip transcript analysis for leave-only and swap flows
        if self.state.flow_type in ("leave_review", "shift_swap"):
            self.state.audit_log.append(
                AuditLogEntry(
                    step_name="analyze_transcripts",
                    event_type="step_skipped",
                    message=f"Skipped for {self.state.flow_type} flow.",
                )
            )
            return

        self._emit("step_started", {"step": "analyze_transcripts"})
        run_transcript_analysis(self.state)
        self._emit("step_completed", {"step": "analyze_transcripts"})

    # ── Steps 3–4: Forecast + Leave in parallel (depend on team_perf) ──
    def _forecast_demand(self) -> None:
        """Invoke the DemandForecaster agent."""
        if self.state.error_state:
            return

        # Skip forecast for training-only, leave, and swap flows
        if self.state.flow_type in ("training", "leave_review", "shift_swap"):
            self.state.audit_log.append(
                AuditLogEntry(
                    step_name="forecast_demand",
                    event_type="step_skipped",
                    message=f"Skipped for {self.state.flow_type} flow.",
                )
            )
            return

        self._emit("step_started", {"step": "forecast_demand"})
        run_demand_forecast(self.state)
        self._emit("step_completed", {"step": "forecast_demand"})

    def _analyze_leave(self) -> None:
        """Invoke the LeaveAnalyzer agent."""
        if self.state.error_state:
            return

        # Skip only for training-only flows
        if self.state.flow_type == "training":
            self.state.audit_log.append(
                AuditLogEntry(
                    step_name="analyze_leave",
                    event_type="step_skipped",
                    message="Skipped for training-only flow.",
                )
            )
            return

        self._emit("step_started", {"step": "analyze_leave"})
        run_leave_analysis(self.state)

        # Emit overlap detection event if overlaps found
        if self.state.leave_report and self.state.leave_report.overlaps:
            self._emit(
                "leave_overlap_detected",
                {
                    "overlaps_count": len(self.state.leave_report.overlaps),
                    "severity": max(
                        (o.severity for o in self.state.leave_report.overlaps),
                        default="low",
                    ),
                },
            )

        self._emit("step_completed", {"step": "analyze_leave"})

    @listen(analyze_transcripts)
    async def run_parallel_post_transcript(self) -> None:
        """Run demand-forecast and/or leave analysis after transcripts.

        Routing logic (fix #8 — avoid unnecessary thread spawning):
        - training:              both steps are skipped → return immediately
        - shift_swap/leave_review: only leave analysis runs → call directly
        - schedule/hybrid:       both run → true parallel via asyncio.gather
        """
        if self.state.error_state:
            return

        flow = self.state.flow_type

        if flow == "training":
            # Both _forecast_demand and _analyze_leave are no-ops for training;
            # skip the asyncio.gather overhead entirely.
            return
        elif flow in ("shift_swap", "leave_review"):
            # Only leave analysis is needed; run it directly in a thread.
            await asyncio.to_thread(self._analyze_leave)
        else:
            # schedule / hybrid: both branches do real work — run in parallel.
            await asyncio.gather(
                asyncio.to_thread(self._forecast_demand),
                asyncio.to_thread(self._analyze_leave),
            )

    # ── Step 5: Router ──
    @router(run_parallel_post_transcript)
    def route_by_flow_type(self) -> str:
        """Route to the appropriate sub-pipeline based on flow_type."""
        if self.state.error_state:
            return "error"

        self.state.audit_log.append(
            AuditLogEntry(
                step_name="router",
                event_type="routing",
                message=f"Routing to '{self.state.flow_type}' path.",
            )
        )
        return self.state.flow_type

    # ── Step 6a: Schedule Generation ──
    @listen("schedule")
    def generate_schedule(self):
        """Invoke the PerfAwareScheduler agent (schedule path)."""
        self._emit("step_started", {"step": "generate_schedule"})
        run_schedule_generation(self.state)
        self._emit("step_completed", {"step": "generate_schedule"})
        return self.state

    # ── Step 6b: Training Design ──
    @listen("training")
    def design_training(self):
        """Invoke the TrainerDesigner agent (training path)."""
        self._emit("step_started", {"step": "design_training"})
        run_training_design(self.state)
        self._emit("step_completed", {"step": "design_training"})
        return self.state

    # ── Step 6c: Hybrid — both schedule and training (PARALLEL) ──
    @listen("hybrid")
    async def run_hybrid_parallel(self):
        """Run schedule and training vertically in parallel."""
        if self.state.error_state:
            return

        def _do_schedule():
            self._emit("step_started", {"step": "generate_schedule"})
            run_schedule_generation(self.state)
            self._emit("step_completed", {"step": "generate_schedule"})

        def _do_training():
            self._emit("step_started", {"step": "design_training"})
            run_training_design(self.state)
            self._emit("step_completed", {"step": "design_training"})

        await asyncio.gather(
            asyncio.to_thread(_do_schedule),
            asyncio.to_thread(_do_training)
        )
        return self.state

    # ── Step 6d: Shift Swap Coordination ──
    @listen("shift_swap")
    def coordinate_swap(self):
        """Invoke the ShiftSwapCoordinator agent."""
        self._emit("step_started", {"step": "coordinate_swap"})
        run_shift_swap_coordination(self.state)

        if self.state.swap_result:
            self._emit(
                "swap_feasibility",
                {
                    "feasible": self.state.swap_result.feasible,
                    "risk_flags": self.state.swap_result.risk_flags,
                },
            )

        self._emit("step_completed", {"step": "coordinate_swap"})
        return self.state

    # ── Step 6e: Leave Review (direct to HITL) ──
    @listen("leave_review")
    def handle_leave_review(self):
        """For leave_review flows, proceed directly to HITL with the report."""
        self.state.audit_log.append(
            AuditLogEntry(
                step_name="leave_review",
                event_type="step_completed",
                message="Leave review ready for manager approval.",
            )
        )
        return self.state

    # ── Step 7: HITL Checkpoint ──
    @listen(or_(
        generate_schedule,
        design_training,
        run_hybrid_parallel,
        coordinate_swap,
        handle_leave_review,
    ))
    def hitl_checkpoint(self) -> None:
        """Pause execution for Human-in-the-Loop validation.

        Sets hitl_status to 'pending' and emits an SSE event.
        The flow resumes when the API calls resume_after_hitl().
        """
        if self.state.error_state:
            return

        self.state.current_step = "hitl_checkpoint"
        self.state.hitl_status = "pending"

        pending_outputs: list[str] = []
        if self.state.schedule_output:
            pending_outputs.append("schedule_output")
        if self.state.training_plan:
            pending_outputs.append("training_plan")
        if self.state.swap_result:
            pending_outputs.append("swap_result")
        if self.state.leave_report:
            pending_outputs.append("leave_report")

        self.state.audit_log.append(
            AuditLogEntry(
                step_name="hitl_checkpoint",
                event_type="hitl_required",
                message=f"HITL approval required for: {', '.join(pending_outputs)}",
                data={"pending_outputs": pending_outputs},
            )
        )

        self._emit(
            "hitl_required",
            {"pending_outputs": pending_outputs},
        )

        # Pause the synchronous thread until the API receives a decision
        # and calls resume_after_hitl(), which sets the event.
        self._hitl_event.wait()


    # ── Step 8: Finalize ──
    @listen(hitl_checkpoint)
    def finalize(self) -> None:
        """Finalize the flow after HITL decision."""
        self.state.current_step = "finalize"

        if self._hitl_decision:
            decision = self._hitl_decision.decision
            self.state.hitl_status = (
                "approved" if decision == "approve"
                else "edited" if decision == "edit"
                else "rejected"
            )

            self.state.audit_log.append(
                AuditLogEntry(
                    step_name="finalize",
                    event_type="hitl_resolved",
                    message=(
                        f"HITL decision: {decision} by "
                        f"{self._hitl_decision.reviewer_id}"
                    ),
                    data={
                        "decision": decision,
                        "reviewer_id": self._hitl_decision.reviewer_id,
                        "comments": self._hitl_decision.comments,
                    },
                )
            )
            self._emit(
                "hitl_resolved",
                {
                    "decision": decision,
                    "reviewer_id": self._hitl_decision.reviewer_id,
                },
            )

        # ── Send results email via Gmail API ──
        import os
        manager_email = os.getenv("MANAGER_EMAIL", "")
        if manager_email and self.state.hitl_status in ("approved", "edited"):
            try:
                from utils.mcp_client import mcp_client

                # Build HTML email body
                body_parts = [
                    f"<h2>BPO Ops Superflow — Results</h2>",
                    f"<p><b>Run ID:</b> {self.state.run_id}</p>",
                    f"<p><b>Flow Type:</b> {self.state.flow_type}</p>",
                    f"<p><b>Queue:</b> {self.state.queue_id}</p>",
                    f"<p><b>Time Window:</b> {self.state.time_window}</p>",
                    f"<p><b>Status:</b> {self.state.hitl_status}</p>",
                ]

                if self.state.schedule_output:
                    body_parts.append(
                        f"<h3>Schedule</h3>"
                        f"<p>Coverage Score: {self.state.schedule_output.coverage_score}</p>"
                        f"<p>Assignments: {len(self.state.schedule_output.assignments)}</p>"
                    )
                if self.state.training_plan:
                    body_parts.append(
                        f"<h3>Training Plan</h3>"
                        f"<p>Recommendations: {len(self.state.training_plan.recommendations)}</p>"
                        f"<p>Priority Agents: {', '.join(self.state.training_plan.priority_agents)}</p>"
                    )
                if self.state.swap_result:
                    body_parts.append(
                        f"<h3>Shift Swap</h3>"
                        f"<p>Feasible: {self.state.swap_result.feasible}</p>"
                        f"<p>Recommendation: {self.state.swap_result.recommendation}</p>"
                    )
                if self.state.leave_report:
                    body_parts.append(
                        f"<h3>Leave Report</h3>"
                        f"<p>Overlaps: {len(self.state.leave_report.overlaps)}</p>"
                        f"<p>Coverage Gaps: {len(self.state.leave_report.coverage_gaps)}</p>"
                    )

                body_html = "\n".join(body_parts)

                result = mcp_client.call_tool_sync(
                    "send_results_email",
                    {
                        "to_email": manager_email,
                        "subject": f"BPO Flow Results — {self.state.flow_type} ({self.state.hitl_status})",
                        "body_html": body_html,
                        "run_id": self.state.run_id,
                    },
                )

                self.state.audit_log.append(
                    AuditLogEntry(
                        step_name="finalize",
                        event_type="email_sent",
                        message=f"Results email sent to {manager_email}.",
                        data=result if isinstance(result, dict) else {"raw": str(result)},
                    )
                )
            except Exception as email_err:
                print(f"[WARN] Failed to send results email: {email_err}")
                self.state.audit_log.append(
                    AuditLogEntry(
                        step_name="finalize",
                        event_type="email_failed",
                        message=f"Failed to send results email: {email_err}",
                    )
                )

        self.state.audit_log.append(
            AuditLogEntry(
                step_name="finalize",
                event_type="flow_completed",
                message=f"Flow completed with status: {self.state.hitl_status}.",
            )
        )
        self._emit(
            "flow_completed",
            {"final_status": self.state.hitl_status},
        )

    # ── Error Sink ──
    @listen("error")
    def handle_error(self) -> None:
        """Handle routing errors."""
        self.state.audit_log.append(
            AuditLogEntry(
                step_name="error_handler",
                event_type="flow_error",
                message=f"Flow error: {self.state.error_state}",
            )
        )
        if self.state.error_state:
            self._emit(
                "flow_error",
                {
                    "error_type": self.state.error_state.error_type,
                    "message": self.state.error_state.message,
                },
            )

    # ── Public API for HITL Resume ──
    def resume_after_hitl(self, decision: HITLDecision) -> None:
        """Called by the API layer to resume the flow after HITL decision.

        Args:
            decision: The manager's HITL decision.
        """
        self._hitl_decision = decision
        self._hitl_event.set()
