"""
Transcript Analyzer Agent

Connects to the FastMCP server to fetch PII-redacted transcripts
and computes team performance metrics.
"""

import concurrent.futures
import os

from crewai import Agent, Crew, Task
from pydantic import ValidationError

from models.state import (
    AgentPerf,
    AuditLogEntry,
    BPOFlowState,
    ErrorDetail,
    RedactedTranscript,
    TeamPerfMetrics,
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
transcript_analyzer_agent = Agent(
    role="Transcript Analyzer",
    goal=(
        "Read each PII-redacted call transcript, score every agent on five dimensions "
        "(average handle time, CSAT, first-call resolution rate, escalation rate, "
        "and schedule adherence), list each agent's top strengths and skill gaps, "
        "then compute team-level averages for handle time, CSAT, and FCR."
    ),
    backstory=(
        "You are a senior BPO quality-assurance analyst with 10+ years of "
        "experience scoring contact-center interactions. You evaluate transcripts "
        "specific transcript evidence (e.g., quoting phrases that show empathy "
        "or missed upsell opportunities). **CRITICAL INSTRUCTION**: You MUST use the "
        "explicit quantitative scores provided in the Agent Performance Data. Do NOT "
        "attempt to estimate or reinvent CSAT, AHT, or FCR mathematically. Your job is "
        "purely qualitative analysis (identifying the strengths and gaps) to explain "
        "those hard numbers."
    ),
    llm=MODEL_NAME,
    verbose=False,
    allow_delegation=False,
    max_iter=2,
)


def run_transcript_analysis(state: BPOFlowState) -> BPOFlowState:
    """Execute the transcript analysis step.

    Invokes the MCP tool to fetch transcripts (in parallel with performance
    metrics), then uses the agent to compute team performance metrics with
    qualitative strengths/gaps enrichment.

    Args:
        state: The current flow state.

    Returns:
        Updated flow state with team_perf populated.
    """
    state.current_step = "analyze_transcripts"
    state.audit_log.append(
        AuditLogEntry(
            step_name="analyze_transcripts",
            event_type="step_started",
            message="Starting transcript analysis via MCP.",
        )
    )

    try:
        from utils.mcp_client import mcp_client

        # ── Fix #7: Fetch transcripts and agent metrics in PARALLEL ──
        raw_transcripts = []
        raw_metrics = []

        def _fetch_transcripts():
            return mcp_client.call_tool_sync(
                "get_transcripts",
                {"queue_id": state.queue_id, "time_window": state.time_window},
            )

        def _fetch_metrics():
            return mcp_client.call_tool_sync(
                "get_agent_performance_data",
                {"queue_id": state.queue_id},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            future_transcripts = ex.submit(_fetch_transcripts)
            future_metrics = ex.submit(_fetch_metrics)

            # Collect transcripts result
            try:
                raw_transcripts = future_transcripts.result(timeout=60)
                state.transcripts = [RedactedTranscript(**t) for t in raw_transcripts]
                state.audit_log.append(
                    AuditLogEntry(
                        step_name="analyze_transcripts",
                        event_type="data_fetched",
                        message=f"Retrieved {len(state.transcripts)} transcripts to analyze.",
                    )
                )
            except Exception as mcp_err:
                print(f"[ERROR] MCP transcript call failed ({mcp_err}). No transcript data available.")
                state.transcripts = []
                state.audit_log.append(
                    AuditLogEntry(
                        step_name="analyze_transcripts",
                        event_type="data_fetched_error",
                        message=f"MCP unavailable — could not fetch transcript data: {mcp_err}",
                    )
                )

            # Collect metrics result
            try:
                raw_metrics = future_metrics.result(timeout=60)
                agents = [AgentPerf(**m) for m in raw_metrics]
                avg_ht = sum(a.avg_handle_time_seconds for a in agents) / len(agents) if agents else 0
                avg_csat = sum(a.csat_score for a in agents) / len(agents) if agents else 0
                avg_fcr = sum(a.fcr_rate for a in agents) / len(agents) if agents else 0
                # Build a baseline team_perf from raw MCP data (used as fallback)
                state.team_perf = TeamPerfMetrics(
                    agents=agents,
                    team_avg_handle_time=round(avg_ht, 1),
                    team_avg_csat=round(avg_csat, 2),
                    team_avg_fcr=round(avg_fcr, 2),
                )
                state.audit_log.append(
                    AuditLogEntry(
                        step_name="analyze_transcripts",
                        event_type="data_fetched",
                        message=f"Retrieved performance metrics for {len(agents)} agents.",
                    )
                )
            except Exception as perf_err:
                print(f"[ERROR] MCP perf data call failed ({perf_err}). No metrics available.")
                state.team_perf = TeamPerfMetrics(
                    agents=[],
                    team_avg_handle_time=0.0,
                    team_avg_csat=0.0,
                    team_avg_fcr=0.0,
                )

        transcript_text = "\n---\n".join(t.content for t in state.transcripts) or "No transcripts available."

        perf_text = "Agent Performance Data (USE THESE EXACT NUMBERS, DO NOT ESTIMATE):\n"
        if state.team_perf and state.team_perf.agents:
            for agent in state.team_perf.agents:
                perf_text += (
                    f"- Agent {agent.agent_id} ({agent.agent_name}): "
                    f"AHT={agent.avg_handle_time_seconds}s, CSAT={agent.csat_score}, "
                    f"FCR={agent.fcr_rate}, Escalation={agent.escalation_rate}\n"
                )
        else:
            perf_text = "Agent Performance Data: (None provided. You may estimate if necessary.)\n"

        task = Task(
            description=(
                f"You have {len(state.transcripts)} PII-redacted call transcripts for "
                f"queue '{state.queue_id}' during '{state.time_window}'.\n\n"
                f"{perf_text}\n\n"
                f"Transcripts:\n{transcript_text}\n\n"
                f"Step 1 — Per-agent scoring. For every agent who appears in the "
                f"transcripts, produce:\n"
                f"  a. avg_handle_time_seconds — USE THE EXACT NUMBER from the Agent Performance Data above. Do not estimate.\n"
                f"  b. csat_score (0-5) — USE THE EXACT NUMBER from the Agent Performance Data above. Do not infer.\n"
                f"  c. fcr_rate (0.0-1.0) — USE THE EXACT NUMBER from the Agent Performance Data above.\n"
                f"  d. escalation_rate (0.0-1.0) — USE THE EXACT NUMBER from the Agent Performance Data above.\n"
                f"  e. schedule_adherence (0.0-1.0) — default to 0.95 when not determinable.\n"
                f"  f. strengths — list of demonstrated skill areas identified by reading the transcripts (e.g., 'empathy', "
                f"     'product knowledge', 'first-call resolution')\n"
                f"  g. gaps — list of areas needing improvement identified by reading the transcripts (e.g., 'upselling', "
                f"     'call control')\n\n"
                f"Step 2 — Team averages. Compute:\n"
                f"  - team_avg_handle_time (mean of all agents' avg_handle_time_seconds)\n"
                f"  - team_avg_csat (mean of all agents' csat_score)\n"
                f"  - team_avg_fcr (mean of all agents' fcr_rate)"
            ),
            expected_output=(
                "Return a JSON object with two keys: 'agents' (a list of per-agent "
                "objects each containing agent_id, agent_name, avg_handle_time_seconds, "
                "csat_score, fcr_rate, escalation_rate, schedule_adherence, strengths, "
                "and gaps) and team-level averages (team_avg_handle_time, "
                "team_avg_csat, team_avg_fcr). "
                "Return strictly valid raw JSON with no Markdown wrappers, no backticks, and no conversational text. Start directly with { and end with }."
            ),
            agent=transcript_analyzer_agent,
            # Fix #1: capture structured LLM output so strengths/gaps are stored
            output_pydantic=TeamPerfMetrics,
        )

        result = _run_crew(transcript_analyzer_agent, task)

        # Fix #1: save LLM-enriched result (with strengths/gaps) back to state.
        # Fall back to the raw-MCP-derived team_perf if the LLM output is unusable.
        if result.pydantic and isinstance(result.pydantic, TeamPerfMetrics):
            state.team_perf = result.pydantic
            state.audit_log.append(
                AuditLogEntry(
                    step_name="analyze_transcripts",
                    event_type="step_completed",
                    message=(
                        f"Transcript analysis complete. LLM-enriched metrics saved for "
                        f"{len(state.team_perf.agents)} agents."
                    ),
                )
            )
        else:
            # LLM failed to return structured output — keep the raw-MCP fallback
            state.audit_log.append(
                AuditLogEntry(
                    step_name="analyze_transcripts",
                    event_type="step_completed",
                    message=(
                        f"Transcript analysis complete (LLM output unparseable — "
                        f"using raw MCP metrics for {len(state.team_perf.agents) if state.team_perf else 0} agents)."
                    ),
                )
            )

    except ValidationError as e:
        state.error_state = ErrorDetail(
            step_name="analyze_transcripts",
            error_type="ValidationError",
            message=f"Failed to validate transcript data: {e}",
            recoverable=False,
        )
    except ConnectionError as e:
        state.error_state = ErrorDetail(
            step_name="analyze_transcripts",
            error_type="MCPConnectionError",
            message=f"Failed to connect to MCP server: {e}",
            recoverable=True,
        )

    return state
