"""
Shift Swap Coordinator Agent

Validates shift swap requests between two agents by checking leave
conflicts, computing schedule intersections, and evaluating coverage impact.
"""

import os

from crewai import Agent, Crew, Task
from pydantic import ValidationError

from models.state import (
    AuditLogEntry,
    BPOFlowState,
    ErrorDetail,
    ScheduleIntersection,
    ShiftSwapResult,
)

MODEL_NAME = os.getenv("MODEL_NAME", "gemini/gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _run_crew(agent: "Agent", task: "Task"):
    """Instantiate a single-agent Crew and kick it off.

    Centralises Crew construction so each run_* function doesn't repeat the
    boilerplate, and ensures the module-level Agent singleton is always used.
    """
    return Crew(agents=[agent], tasks=[task]).kickoff()


# ---------------------------------------------------------------------------
# Agent Definition
# ---------------------------------------------------------------------------
shift_swap_coordinator_agent = Agent(
    role="Shift Swap Coordinator",
    goal=(
        "Evaluate a proposed shift swap between two agents by checking "
        "leave conflicts, computing their schedule intersection "
        "(shared shift dates, shared leave dates, overlapping availability), "
        "assessing coverage impact, identifying risk flags, and delivering "
        "a clear feasible/infeasible verdict with a written recommendation."
    ),
    backstory=(
        "You are a BPO scheduling operations expert. You evaluate every "
        "swap against four criteria: (1) neither agent is on approved "
        "leave on the swap date, (2) both agents meet a minimum 8-hour "
        "rest period before and after the swapped shift, (3) neither "
        "agent exceeds 48 weekly hours post-swap, and (4) the swap "
        "maintains or improves the queue's coverage score."
    ),
    llm=MODEL_NAME,
    verbose=False,
    allow_delegation=False,
    max_iter=2,
)


def run_shift_swap_coordination(state: BPOFlowState) -> BPOFlowState:
    """Execute the shift swap coordination step.

    Args:
        state: The current flow state with leave_report and swap_request populated.

    Returns:
        Updated flow state with swap_result populated.
    """
    state.current_step = "coordinate_swap"
    state.audit_log.append(
        AuditLogEntry(
            step_name="coordinate_swap",
            event_type="step_started",
            message="Starting shift swap feasibility analysis.",
        )
    )

    if state.swap_request is None:
        state.error_state = ErrorDetail(
            step_name="coordinate_swap",
            error_type="ValidationError",
            message="No swap_request provided for shift_swap flow type.",
            recoverable=False,
        )
        return state

    try:
        swap = state.swap_request
        leave_context = "No leave data available."
        if state.leave_report:
            leave_context = (
                f"Active leaves: {len(state.leave_report.agent_leaves)}, "
                f"Overlaps: {len(state.leave_report.overlaps)}"
            )

        try:
            from utils.mcp_client import mcp_client
            # Fetch schedules for the two agents involved in the swap
            raw_schedules = mcp_client.call_tool_sync(
                "get_weekly_schedules",
                {"agent_ids": [swap.agent_a_id, swap.agent_b_id]}
            )
            
            if raw_schedules:
                schedule_text = f"Current Weekly Schedules for {swap.agent_a_id} and {swap.agent_b_id}:\n"
                for entry in raw_schedules:
                    schedule_text += f"  - Agent: {entry.get('agent_id')}, Date: {entry.get('shift_date')}, Start: {entry.get('start_time')}, End: {entry.get('end_time')}\n"
            else:
                schedule_text = f"Weekly Schedules: (No schedules found for these agents. Cannot verify rest periods.)"

            state.audit_log.append(
                AuditLogEntry(
                    step_name="coordinate_swap",
                    event_type="data_fetched",
                    message=f"Fetched {len(raw_schedules)} weekly schedule records from MCP.",
                )
            )
        except Exception as schedule_err:
            print(f"[ERROR] MCP schedules call failed: {schedule_err}")
            schedule_text = "Weekly Schedules unavailable due to MCP error."

        task = Task(
            description=(
                f"Evaluate this shift swap request:\n"
                f"  • Agent A: {swap.agent_a_id} (shift: {swap.shift_a_id})\n"
                f"  • Agent B: {swap.agent_b_id} (shift: {swap.shift_b_id})\n"
                f"  • Swap date: {swap.shift_date}\n"
                f"  • Reason: {swap.reason}\n\n"
                f"Leave constraints: {leave_context}\n\n"
                f"{schedule_text}\n\n"
                f"Complete these checks in order:\n"
                f"  1. Leave conflict check: Confirm neither agent has approved leave "
                f"     covering {swap.shift_date} (from Leave constraints above). If either does, set feasible=False.\n"
                f"  2. Rest-period check: Look at the Current Weekly Schedules above. "
                f"     If the swap happens, verify both agents will still have at least 8 hours "
                f"     of rest between their new shifts and adjacent shifts.\n"
                f"  3. Weekly-hours check: Confirm neither agent would exceed 48 "
                f"     weekly hours after the swap.\n"
                f"  4. Coverage-impact assessment: Determine whether the swap "
                f"     maintains or improves the queue's coverage score.\n"
                f"  5. Produce a schedule intersection: list shared_shift_dates, "
                f"     shared_leave_dates, and overlapping_availability_windows "
                f"     between the two agents.\n"
                f"  6. List any risk_flags (e.g., 'Agent A already at 44 weekly hours').\n"
                f"  7. Set feasible=True or feasible=False and write a one-paragraph "
                f"     recommendation."
            ),
            expected_output=(
                "Return a JSON object with: feasible (boolean), "
                "agent_a_schedule_summary, agent_b_schedule_summary, "
                "intersection (object with shared_shift_dates, shared_leave_dates, "
                "overlapping_availability_windows, swap_compatible), "
                "coverage_impact (string), risk_flags (list of strings), "
                "and recommendation (string). "
                "Return strictly valid raw JSON with no Markdown wrappers, no backticks, and no conversational text. Start directly with { and end with }."
            ),
            agent=shift_swap_coordinator_agent,
            output_pydantic=ShiftSwapResult,
        )

        result = _run_crew(shift_swap_coordinator_agent, task)

        if result.pydantic:
            state.swap_result = result.pydantic
        else:
            raise ValueError("LLM failed to return structured ShiftSwapResult data")

        state.audit_log.append(
            AuditLogEntry(
                step_name="coordinate_swap",
                event_type="step_completed",
                message=(
                    f"Swap analysis complete for {swap.agent_a_id} <-> {swap.agent_b_id}."
                ),
            )
        )

    except ValidationError as e:
        state.error_state = ErrorDetail(
            step_name="coordinate_swap",
            error_type="ValidationError",
            message=f"Swap data validation failed: {e}",
            recoverable=False,
        )

    return state
