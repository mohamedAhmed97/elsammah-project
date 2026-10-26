"""
Demand Forecaster Agent

Analyzes historical call volume patterns to generate staffing
requirement predictions per time slot.
"""

import os

from crewai import Agent, Crew, Task
from pydantic import ValidationError

from models.state import (
    AuditLogEntry,
    BPOFlowState,
    DemandForecast,
    ErrorDetail,
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
demand_forecaster_agent = Agent(
    role="Demand Forecaster",
    goal=(
        "Produce a time-slot-level call-volume forecast and staffing plan. "
        "For each slot (morning, afternoon, evening), predict the expected "
        "call count and the minimum number of agents required to maintain "
        "the SLA. Compute the total predicted volume across all slots."
    ),
    backstory=(
        "You are a workforce planning expert who has built time-series "
        "forecasting models for large multi-site contact centers. You factor "
        "in day-of-week seasonality, holiday spikes, marketing campaign "
        "schedules, and queue-specific volume patterns (e.g., billing queues "
        "peak on invoice dates)."
    ),
    llm=MODEL_NAME,
    verbose=False,
    allow_delegation=False,
    max_iter=2,
)


def run_demand_forecast(state: BPOFlowState) -> BPOFlowState:
    """Execute the demand forecasting step.

    Args:
        state: The current flow state with team_perf populated.

    Returns:
        Updated flow state with demand_forecast populated.
    """
    state.current_step = "forecast_demand"
    state.audit_log.append(
        AuditLogEntry(
            step_name="forecast_demand",
            event_type="step_started",
            message="Starting demand forecast analysis.",
        )
    )

    try:
        perf_summary = "No performance data available."
        if state.team_perf:
            perf_summary = (
                f"Team avg handle time: {state.team_perf.team_avg_handle_time}s, "
                f"Team avg CSAT: {state.team_perf.team_avg_csat}, "
                f"Team avg FCR: {state.team_perf.team_avg_fcr}"
            )

        try:
            from utils.mcp_client import mcp_client
            raw_demand = mcp_client.call_tool_sync(
                "get_historical_demand",
                {"queue_id": state.queue_id, "time_window": state.time_window}
            )
            
            if raw_demand:
                demand_text = "Historical Demand Context:\n"
                for entry in raw_demand:
                    demand_text += f"- Date: {entry.get('date')}, Slot: {entry.get('time_slot')}, Vol: {entry.get('call_volume')}, AHT: {entry.get('avg_handle_time')}s, SLA: {entry.get('service_level')}%\n"
            else:
                demand_text = "No historical demand data available."
                
            state.audit_log.append(
                AuditLogEntry(
                    step_name="forecast_demand",
                    event_type="data_fetched",
                    message=f"Fetched {len(raw_demand)} historical demand records from MCP server.",
                )
            )
        except Exception as mcp_err:
            print(f"[ERROR] MCP call failed ({mcp_err}). No historical demand data available.")
            demand_text = "No historical demand data available due to MCP error."
            state.audit_log.append(
                AuditLogEntry(
                    step_name="forecast_demand",
                    event_type="data_fetched_error",
                    message=f"MCP unavailable — could not fetch historical demand: {mcp_err}",
                )
            )

        from models.state import DemandForecast, TimeSlot
        
        task = Task(
            description=(
                f"Forecast call demand for queue '{state.queue_id}' during period "
                f"'{state.time_window}'.\n\n"
                f"Current team performance context:\n{perf_summary}\n\n"
                f"{demand_text}\n\n"
                f"Generate a forecast with exactly three time slots:\n"
                f"  1. Morning   (start_time='06:00', end_time='14:00')\n"
                f"  2. Afternoon (start_time='14:00', end_time='22:00')\n"
                f"  3. Evening   (start_time='22:00', end_time='06:00')\n\n"
                f"For each slot provide:\n"
                f"  - predicted_volume (integer) — expected number of inbound calls (anchor this to historical data if available)\n"
                f"  - required_agents (integer) — minimum agents needed to stay within "
                f"    SLA (target: 80%% of calls answered within 30 seconds)\n\n"
                f"Also compute:\n"
                f"  - total_predicted_volume — sum of all slot volumes\n"
            ),
            expected_output=(
                "Return a JSON object containing: forecast_period (string), "
                "slots (list of objects with start_time, end_time, "
                "predicted_volume, required_agents), and total_predicted_volume "
                "(integer). "
                "Return strictly valid raw JSON with no Markdown wrappers, no backticks, and no conversational text. Start directly with { and end with }."
            ),
            agent=demand_forecaster_agent,
            output_pydantic=DemandForecast,
        )

        result = _run_crew(demand_forecaster_agent, task)

        if result.pydantic:
            state.demand_forecast = result.pydantic
            state.demand_forecast.forecast_period = state.time_window
        else:
            raise ValueError("LLM failed to return structured DemandForecast data")

        state.audit_log.append(
            AuditLogEntry(
                step_name="forecast_demand",
                event_type="step_completed",
                message="Demand forecast generated.",
            )
        )

    except ValidationError as e:
        state.error_state = ErrorDetail(
            step_name="forecast_demand",
            error_type="ValidationError",
            message=f"Forecast data validation failed: {e}",
            recoverable=False,
        )

    return state
