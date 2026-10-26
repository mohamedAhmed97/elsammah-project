"""
Leave Analyzer — Deterministic Analysis (No LLM)

Fetches leave data via MCP, then uses pure Python logic to detect
overlapping absences, compute coverage gaps, and classify severity.
No LLM call is needed — all analysis is deterministic.
"""

from datetime import datetime, timedelta

from pydantic import ValidationError

from models.state import (
    AgentLeave,
    AuditLogEntry,
    BPOFlowState,
    CoverageGap,
    ErrorDetail,
    LeaveOverlap,
    LeaveReport,
)


def _normalize_date(val: str) -> str:
    """Convert various date formats to YYYY-MM-DD."""
    if not val:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return val  # return as-is if nothing matches


def run_leave_analysis(state: BPOFlowState) -> BPOFlowState:
    """Execute the leave analysis step (deterministic, no LLM).

    Fetches leave data (via MCP), detects overlaps, computes coverage gaps,
    and classifies severity — all via Python logic.

    Args:
        state: The current flow state.

    Returns:
        Updated flow state with leave_report populated.
    """
    state.current_step = "analyze_leave"
    state.audit_log.append(
        AuditLogEntry(
            step_name="analyze_leave",
            event_type="step_started",
            message="Starting leave analysis and overlap detection (deterministic).",
        )
    )

    try:
        # ── Fetch leave data via MCP ──
        raw_leave_data = []
        try:
            from utils.mcp_client import mcp_client
            raw_leave_data = mcp_client.call_tool_sync(
                "get_agent_leave_data",
                {"queue_id": state.queue_id, "time_window": state.time_window}
            )
            state.audit_log.append(AuditLogEntry(
                step_name="analyze_leave",
                event_type="data_fetched",
                message=f"Fetched {len(raw_leave_data)} leave records from MCP server.",
            ))
        except Exception as mcp_err:
            # IMPORTANT: Do not proceed with hardcoded/mock leave data.
            # Leave data directly impacts compliance and staffing decisions.
            print(f"[ERROR] MCP leave data call failed ({mcp_err}). Aborting leave analysis.")
            state.error_state = ErrorDetail(
                step_name="analyze_leave",
                error_type="MCPConnectionError",
                message=f"MCP unavailable — could not fetch leave data: {mcp_err}",
                recoverable=True,
            )
            state.audit_log.append(
                AuditLogEntry(
                    step_name="analyze_leave",
                    event_type="data_fetched_error",
                    message=f"MCP unavailable — could not fetch leave data: {mcp_err}",
                )
            )
            return state

        # ── Parse leave records into AgentLeave objects ──
        agent_leaves = []
        if isinstance(raw_leave_data, list):
            for rec in raw_leave_data:
                if isinstance(rec, dict):
                    try:
                        agent_leaves.append(AgentLeave(
                            agent_id=rec.get("agent_id", ""),
                            agent_name=rec.get("agent_name", ""),
                            leave_type=rec.get("leave_type", "annual"),
                            start_date=_normalize_date(rec.get("start_date", "")),
                            end_date=_normalize_date(rec.get("end_date", "")),
                            remaining_balance_days=float(rec.get("remaining_balance_days", 0)),
                            status=rec.get("status", "pending"),
                        ))
                    except Exception as parse_err:
                        print(f"[WARN] Skipping leave record: {parse_err}")

        # ── Detect overlapping absences ──
        overlaps = []
        for i, a in enumerate(agent_leaves):
            for b in agent_leaves[i + 1:]:
                overlap_start = max(a.start_date, b.start_date)
                overlap_end = min(a.end_date, b.end_date)
                if overlap_start <= overlap_end:
                    overlap_days = (overlap_end - overlap_start).days + 1
                    severity = "low" if overlap_days <= 1 else ("medium" if overlap_days <= 3 else "critical")
                    overlaps.append(LeaveOverlap(
                        agent_a_id=a.agent_id,
                        agent_b_id=b.agent_id,
                        overlap_start=overlap_start,
                        overlap_end=overlap_end,
                        affected_queue=state.queue_id,
                        severity=severity,
                    ))

        # ── Compute coverage gaps per day ──
        coverage_gaps = []
        # Use actual team size from state if available; avoid the arbitrary +20 magic number.
        if state.team_perf and state.team_perf.agents:
            total_agents = len(state.team_perf.agents)
        else:
            total_agents = max(len(set(al.agent_id for al in agent_leaves)) + 5, 10)
        all_dates = set()
        for al in agent_leaves:
            d = al.start_date
            while d <= al.end_date:
                all_dates.add(d)
                d += timedelta(days=1)

        for day in sorted(all_dates):
            absent = sum(
                1 for al in agent_leaves
                if al.start_date <= day <= al.end_date
            )
            available = total_agents - absent
            coverage_ratio = available / total_agents if total_agents > 0 else 1
            if coverage_ratio < 0.85:
                severity = "low" if coverage_ratio >= 0.8 else ("medium" if coverage_ratio >= 0.6 else "critical")
                coverage_gaps.append(CoverageGap(
                    date=day.strftime("%Y-%m-%d"),
                    queue_id=state.queue_id,
                    available_agents=available,
                    required_agents=total_agents,
                    gap_severity=severity,
                ))

        state.leave_report = LeaveReport(
            report_period=state.time_window,
            agent_leaves=agent_leaves,
            overlaps=overlaps,
            coverage_gaps=coverage_gaps,
        )

        state.audit_log.append(
            AuditLogEntry(
                step_name="analyze_leave",
                event_type="step_completed",
                message="Leave analysis complete. Overlap detection finished.",
            )
        )

    except ValidationError as e:
        state.error_state = ErrorDetail(
            step_name="analyze_leave",
            error_type="ValidationError",
            message=f"Leave data validation failed: {e}",
            recoverable=False,
        )
    except ConnectionError as e:
        state.error_state = ErrorDetail(
            step_name="analyze_leave",
            error_type="MCPConnectionError",
            message=f"Failed to fetch leave data from MCP: {e}",
            recoverable=True,
        )

    return state
