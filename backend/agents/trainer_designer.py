"""
Trainer Designer Agent

Identifies agents with below-threshold metrics and generates
personalized training recommendations.
"""

import os

from crewai import Agent, Crew, Task
from pydantic import ValidationError

from models.state import (
    AuditLogEntry,
    BPOFlowState,
    ErrorDetail,
    TrainingPlan,
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
trainer_designer_agent = Agent(
    role="Training Plan Designer",
    goal=(
        "Review each agent's performance metrics (CSAT, FCR, escalation "
        "rate), identify specific skill gaps, and design a personalized "
        "training recommendation per agent that includes the gap name, "
        "recommended training modules, estimated hours, and priority "
        "(low / medium / high / critical). Also rank the top 3 agents "
        "who need the most immediate training intervention."
    ),
    backstory=(
        "You are a learning & development specialist with deep BPO "
        "domain knowledge. You rigorously match the agent's performance "
        "gaps to explicit modules from the provided Corporate Course Catalog. "
        "You NEVER invent or 'hallucinate' courses. You only assign courses "
        "that are listed in the catalog, and you strictly use their defined "
        "duration hours. You assign urgency priority based on how far the "
        "agent's score is from the team benchmark."
    ),
    llm=MODEL_NAME,
    verbose=False,
    allow_delegation=False,
    max_iter=2,
)


def run_training_design(state: BPOFlowState) -> BPOFlowState:
    """Execute the training plan design step.

    Args:
        state: The current flow state with team_perf populated.

    Returns:
        Updated flow state with training_plan populated.
    """
    state.current_step = "design_training"
    state.audit_log.append(
        AuditLogEntry(
            step_name="design_training",
            event_type="step_started",
            message="Starting training plan design.",
        )
    )

    try:
        perf_context = "No performance data available."
        if state.team_perf:
            agent_summaries = []
            for a in state.team_perf.agents:
                agent_summaries.append(
                    f"  - {a.agent_name} ({a.agent_id}): "
                    f"CSAT={a.csat_score}, FCR={a.fcr_rate}, "
                    f"Escalation={a.escalation_rate}"
                )
            perf_context = "\n".join(agent_summaries) or "No agents."

        try:
            from utils.mcp_client import mcp_client
            raw_catalog = mcp_client.call_tool_sync("get_course_catalog", {})
            if raw_catalog:
                catalog_text = "Corporate Course Catalog (ONLY select courses from this list):\n"
                for course in raw_catalog:
                    catalog_text += f"  - ID: {course.get('course_id')}, Name: '{course.get('course_name')}', Duration: {course.get('duration_hours')} hrs, Target Gap: {course.get('target_skill_gap')}\n"
            else:
                catalog_text = "Course Catalog: (No catalog available. Please advise manager review.)"
            
            state.audit_log.append(
                AuditLogEntry(
                    step_name="design_training",
                    event_type="data_fetched",
                    message=f"Fetched {len(raw_catalog)} courses from MCP catalog.",
                )
            )
        except Exception as catalog_err:
            print(f"[ERROR] MCP catalog call failed: {catalog_err}")
            catalog_text = "Course Catalog unavailable due to MCP error."

        from models.state import TrainingPlan
        
        task = Task(
            description=(
                f"Design a training plan for queue '{state.queue_id}' covering "
                f"'{state.time_window}'.\n\n"
                f"Agent performance data:\n{perf_context}\n\n"
                f"{catalog_text}\n\n"
                f"Step 1 — Gap analysis: For each agent listed above, compare "
                f"their CSAT, FCR, and escalation_rate to the team average. Flag "
                f"any metric where the agent is >10%% worse than the team mean.\n\n"
                f"Step 2 — Training recommendations: For each flagged agent, "
                f"produce:\n"
                f"  a. agent_id — use ONLY the exact IDs from the data above\n"
                f"  b. skill_gaps — list of identified gap names (e.g., 'fcr_rate', 'escalation_rate')\n"
                f"  c. recommended_modules — list of training module names ONLY from the Corporate Course Catalog above.\n"
                f"  d. estimated_hours — total hours strictly calculated from the duration_hours in the catalog above.\n"
                f"  e. priority — 'critical' if any metric is >25%% below team avg, "
                f"     'high' if >15%%, 'medium' if >10%%, 'low' otherwise\n\n"
                f"Step 3 — Priority ranking: List the top 3 agent_ids who need "
                f"the most urgent training, ordered by severity of gaps."
            ),
            expected_output=(
                "Return a JSON object with: plan_period (string), "
                "recommendations (list of objects with agent_id, skill_gaps, "
                "recommended_modules, estimated_hours, priority), and "
                "priority_agents (list of the top 3 agent IDs). Use only "
                "real Agent IDs from the provided data. "
                "Return strictly valid raw JSON with no Markdown wrappers, no backticks, and no conversational text. Start directly with { and end with }."
            ),
            agent=trainer_designer_agent,
            output_pydantic=TrainingPlan,
        )

        result = _run_crew(trainer_designer_agent, task)

        if result.pydantic:
            state.training_plan = result.pydantic
            state.training_plan.plan_period = state.time_window
        else:
            raise ValueError("LLM failed to return structured TrainingPlan data")

        state.audit_log.append(
            AuditLogEntry(
                step_name="design_training",
                event_type="step_completed",
                message="Training plan design complete.",
            )
        )

    except ValidationError as e:
        state.error_state = ErrorDetail(
            step_name="design_training",
            error_type="ValidationError",
            message=f"Training plan validation failed: {e}",
            recoverable=False,
        )

    return state
