"""
Perf-Aware Scheduler Agent

Combines team performance metrics, demand forecasts, and leave data
to generate optimized shift assignments.
"""

import json
import os
import time

from crewai import Agent, Crew, Task
from pydantic import ValidationError

from models.state import (
    AuditLogEntry,
    BPOFlowState,
    ErrorDetail,
    ScheduleOutput,
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
perf_aware_scheduler_agent = Agent(
    role="Performance-Aware Scheduler",
    goal=(
        "Generate an optimized shift schedule that assigns each available "
        "agent to a specific shift window, matching agent strengths to "
        "peak-demand slots, ensuring zero overlap with approved leave dates, "
        "and achieving a coverage_score of at least 0.90. Include a clear "
        "reason for every assignment."
    ),
    backstory=(
        "You are a workforce optimization specialist for BPO operations "
        "with expertise in constraint-based scheduling. You balance three "
        "priorities: (1) skill-to-demand alignment — place high-FCR agents "
        "on high-volume slots; (2) leave-respect — never assign an agent "
        "during approved leave; (3) fairness — distribute shifts evenly "
        "and avoid back-to-back shifts without a minimum 8-hour rest gap."
    ),
    llm=MODEL_NAME,
    verbose=False,
    allow_delegation=False,
    max_iter=2,
)


def run_schedule_generation(state: BPOFlowState) -> BPOFlowState:
    """Execute the schedule generation step.

    Args:
        state: The current flow state with team_perf, demand_forecast,
               and leave_report populated.

    Returns:
        Updated flow state with schedule_output populated.
    """
    state.current_step = "generate_schedule"
    state.audit_log.append(
        AuditLogEntry(
            step_name="generate_schedule",
            event_type="step_started",
            message="Starting performance-aware schedule generation.",
        )
    )

    try:
        # Build context from prior pipeline stages
        perf_context = "No performance data."
        available_agents = []
        if state.team_perf:
            for a in state.team_perf.agents:
                available_agents.append(
                    f"Agent: {a.agent_name} (ID: {a.agent_id}) - "
                    f"Strengths: {', '.join(a.strengths) if a.strengths else 'None'}."
                )
            perf_context = (
                f"Team size: {len(state.team_perf.agents)}, "
                f"Avg handle time: {state.team_perf.team_avg_handle_time}s, "
                f"Avg CSAT: {state.team_perf.team_avg_csat}\n"
                f"Agent Details:\n" + "\n".join(available_agents)
            )

        forecast_context = "No forecast data."
        if state.demand_forecast:
            forecast_context = (
                f"Period: {state.demand_forecast.forecast_period}, "
                f"Predicted volume: {state.demand_forecast.total_predicted_volume}, "
                f"Time slots: {len(state.demand_forecast.slots)}"
            )

        leave_context = "No leave data."
        if state.leave_report:
            leave_details = []
            for leave in state.leave_report.agent_leaves:
                leave_details.append(f"{leave.agent_id} ({leave.agent_name}) is on leave from {leave.start_date} to {leave.end_date}.")
            
            leave_context = (
                f"Active leaves: {len(state.leave_report.agent_leaves)}, "
                f"Detected overlaps: {len(state.leave_report.overlaps)}, "
                f"Coverage gaps: {len(state.leave_report.coverage_gaps)}\n"
                f"Leave Details:\n" + "\n".join(leave_details)
            )

        try:
            from utils.mcp_client import mcp_client
            raw_avail = mcp_client.call_tool_sync("get_agent_availability", {})
            if raw_avail:
                avail_text = "Agent Weekly Availability Matrix:\n"
                for entry in raw_avail:
                    avail_text += f"  - ID: {entry.get('agent_id')}, Max Hrs: {entry.get('max_weekly_hours')}, Current Scheduled Hrs: {entry.get('current_scheduled_hours')}, Pref: {entry.get('preferred_shift')}\n"
            else:
                avail_text = "Agent Availability: (No availability data found. Assume 40 hrs max.)"

            state.audit_log.append(
                AuditLogEntry(
                    step_name="generate_schedule",
                    event_type="data_fetched",
                    message=f"Fetched {len(raw_avail)} agent availability records from MCP.",
                )
            )
        except Exception as avail_err:
            print(f"[ERROR] MCP availability call failed: {avail_err}")
            avail_text = "Agent Availability unavailable due to MCP error."

        from models.state import ScheduleOutput

        task = Task(
            description=(
                f"Generate an optimized shift schedule for queue '{state.queue_id}' "
                f"during '{state.time_window}'.\n\n"
                f"Performance data: {perf_context}\n"
                f"Demand forecast: {forecast_context}\n"
                f"Leave constraints: {leave_context}\n\n"
                f"{avail_text}\n\n"
                f"Scheduling rules (follow strictly):\n"
                f"1. Use ONLY the exact Agent IDs listed in 'Agent Details' above.\n"
                f"2. Match each agent's strengths to the slot with highest demand for "
                f"   that skill.\n"
                f"3. Verify each agent is available on the assigned date — skip any "
                f"   agent whose approved leave covers that date.\n"
                f"4. Ensure every time slot has at least the number of agents specified "
                f"   by the demand forecast's required_agents.\n"
                f"5. **CRITICAL LABOR COMPLIANCE**: Calculate the hours for each new shift you assign (8 hours per shift). "
                f"   Add it to their 'Current Scheduled Hrs'. If the total exceeds their 'Max Hrs' from the Availability Matrix, "
                f"   YOU MUST NOT ASSIGN THEM. Skip them and find someone else.\n"
                f"6. Target an overall coverage_score above 0.90.\n"
                f"7. Write a one-sentence 'reason' for each assignment explaining why "
                f"   this agent was chosen for this slot, mentioning their weekly hours remaining."
            ),
            expected_output=(
                "Return a JSON object containing: schedule_period (string), "
                "assignments (list of objects with agent_id, shift_start, "
                "shift_end, assigned_queue, reason), coverage_score (float "
                "between 0 and 1), and notes (summary string). Use only real "
                "Agent IDs from the provided data. "
                "Return strictly valid raw JSON with no Markdown wrappers, no backticks, and no conversational text. Start directly with { and end with }."
            ),
            agent=perf_aware_scheduler_agent,
            output_pydantic=ScheduleOutput,
        )

        print(f"[INFO] Starting CrewAI execution for Scheduler at {time.strftime('%H:%M:%S')}")
        start_time = time.time()
        
        result = _run_crew(perf_aware_scheduler_agent, task)
        
        end_time = time.time()
        execution_duration = end_time - start_time
        print(f"[INFO] Completed CrewAI execution for Scheduler at {time.strftime('%H:%M:%S')} (Duration: {execution_duration:.2f} seconds)")

        if result.pydantic:
            state.schedule_output = result.pydantic
            state.schedule_output.schedule_period = state.time_window
        else:
            raise ValueError("LLM failed to return structured ScheduleOutput data")

        state.audit_log.append(
            AuditLogEntry(
                step_name="generate_schedule",
                event_type="step_completed",
                message="Schedule generation complete.",
            )
        )

    except ValidationError as e:
        state.error_state = ErrorDetail(
            step_name="generate_schedule",
            error_type="ValidationError",
            message=f"Schedule data validation failed: {e}",
            recoverable=False,
        )

    return state
