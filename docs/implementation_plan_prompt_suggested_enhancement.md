# Enhanced Agent Prompts — Implementation Plan

Enhance the `role`, `goal`, `backstory`, and Task `description` / `expected_output` prompts across all 6 BPO agents. Changes follow prompt engineering best practices: be **specific & direct**, state **what to do** (never what *not* to do), and include clear output formatting instructions aligned with each agent's Pydantic schema.

## Proposed Changes

### 1. Transcript Analyzer

#### [MODIFY] [transcript_analyzer.py](file:///c:/Github%20Projects/crew-ai-hackathon-sama3a/backend/agents/transcript_analyzer.py)

**Agent definition (lines 27–39)**

```diff
 role="Transcript Analyzer",
 goal=(
-    "Analyze PII-redacted call transcripts to extract individual and team "
-    "performance metrics including handle time, CSAT, FCR, and escalation rates."
+    "Read each PII-redacted call transcript, score every agent on five dimensions "
+    "(average handle time, CSAT, first-call resolution rate, escalation rate, "
+    "and schedule adherence), list each agent's top strengths and skill gaps, "
+    "then compute team-level averages for handle time, CSAT, and FCR."
 ),
 backstory=(
-    "You are a senior BPO analytics specialist with deep expertise in "
-    "quality assurance and performance benchmarking. You can identify "
-    "patterns in agent interactions and surface actionable insights."
+    "You are a senior BPO quality-assurance analyst with 10+ years of "
+    "experience scoring contact-center interactions. You evaluate transcripts "
+    "against industry-standard rubrics for empathy, resolution efficiency, "
+    "product knowledge, and de-escalation. You always ground your scores in "
+    "specific transcript evidence (e.g., quoting phrases that show empathy "
+    "or missed upsell opportunities)."
 ),
```

**Task description (lines 121–136)**

```diff
 description=(
-    f"Analyze the following {len(state.transcripts)} call transcripts "
-    f"and compute performance metrics for each agent.\n\n"
-    f"Transcripts:\n{transcript_text}\n\n"
-    f"For each agent, determine:\n"
-    f"1. Average handle time assessment\n"
-    f"2. Customer satisfaction indicators\n"
-    f"3. First-call resolution signals\n"
-    f"4. Escalation patterns\n"
-    f"5. Key strengths and gaps"
+    f"You have {len(state.transcripts)} PII-redacted call transcripts for "
+    f"queue '{state.queue_id}' during '{state.time_window}'.\n\n"
+    f"Transcripts:\n{transcript_text}\n\n"
+    f"Step 1 — Per-agent scoring. For every agent who appears in the "
+    f"transcripts, produce:\n"
+    f"  a. avg_handle_time_seconds — estimate from the transcript length "
+    f"     and conversation complexity\n"
+    f"  b. csat_score (0-5) — infer from customer sentiment, tone, and "
+    f"     resolution satisfaction\n"
+    f"  c. fcr_rate (0.0-1.0) — proportion of calls resolved without "
+    f"     follow-up or transfer\n"
+    f"  d. escalation_rate (0.0-1.0) — proportion of calls escalated to "
+    f"     supervisor or another team\n"
+    f"  e. schedule_adherence (0.0-1.0) — default to 0.95 when not "
+    f"     determinable from transcripts\n"
+    f"  f. strengths — list of demonstrated skill areas (e.g., 'empathy', "
+    f"     'product knowledge', 'first-call resolution')\n"
+    f"  g. gaps — list of areas needing improvement (e.g., 'upselling', "
+    f"     'call control')\n\n"
+    f"Step 2 — Team averages. Compute:\n"
+    f"  - team_avg_handle_time (mean of all agents' avg_handle_time_seconds)\n"
+    f"  - team_avg_csat (mean of all agents' csat_score)\n"
+    f"  - team_avg_fcr (mean of all agents' fcr_rate)"
 ),
 expected_output=(
-    "A structured analysis with per-agent metrics and "
-    "team-level averages."
+    "Return a JSON object with two keys: 'agents' (a list of per-agent "
+    "objects each containing agent_id, agent_name, avg_handle_time_seconds, "
+    "csat_score, fcr_rate, escalation_rate, schedule_adherence, strengths, "
+    "and gaps) and team-level averages (team_avg_handle_time, "
+    "team_avg_csat, team_avg_fcr)."
 ),
```

---

### 2. Demand Forecaster

#### [MODIFY] [demand_forecaster.py](file:///c:/Github%20Projects/crew-ai-hackathon-sama3a/backend/agents/demand_forecaster.py)

**Agent definition (lines 25–38)**

```diff
 role="Demand Forecaster",
 goal=(
-    "Predict future call volumes and compute staffing requirements "
-    "per time slot based on historical data and current trends."
+    "Produce a time-slot-level call-volume forecast and staffing plan. "
+    "For each slot (morning, afternoon, evening), predict the expected "
+    "call count and the minimum number of agents required to maintain "
+    "the SLA. Assign a confidence score (0.0-1.0) to the overall forecast "
+    "and compute the total predicted volume across all slots."
 ),
 backstory=(
-    "You are a workforce planning expert with experience in time-series "
-    "forecasting for contact centers. You understand seasonal patterns, "
-    "campaign impacts, and queue-specific volume drivers."
+    "You are a workforce planning expert who has built time-series "
+    "forecasting models for large multi-site contact centers. You factor "
+    "in day-of-week seasonality, holiday spikes, marketing campaign "
+    "schedules, and queue-specific volume patterns (e.g., billing queues "
+    "peak on invoice dates). You always express uncertainty through an "
+    "explicit confidence score rather than hedging language."
 ),
```

**Task description (lines 70–84)**

```diff
 description=(
-    f"Forecast call demand for queue '{state.queue_id}' "
-    f"during period '{state.time_window}'.\n\n"
-    f"Current team performance:\n{perf_summary}\n\n"
-    f"Based on historical patterns, predict:\n"
-    f"1. Expected call volume per time slot (morning, afternoon, evening)\n"
-    f"2. Required agent count per slot to maintain SLA\n"
-    f"3. Confidence score for the prediction\n"
-    f"4. Total predicted volume for the period"
+    f"Forecast call demand for queue '{state.queue_id}' during period "
+    f"'{state.time_window}'.\n\n"
+    f"Current team performance context:\n{perf_summary}\n\n"
+    f"Generate a forecast with exactly three time slots:\n"
+    f"  1. Morning   (start_time='06:00', end_time='14:00')\n"
+    f"  2. Afternoon (start_time='14:00', end_time='22:00')\n"
+    f"  3. Evening   (start_time='22:00', end_time='06:00')\n\n"
+    f"For each slot provide:\n"
+    f"  - predicted_volume (integer) — expected number of inbound calls\n"
+    f"  - required_agents (integer) — minimum agents needed to stay within "
+    f"    SLA (target: 80% of calls answered within 30 seconds)\n\n"
+    f"Also compute:\n"
+    f"  - total_predicted_volume — sum of all slot volumes\n"
+    f"  - confidence_score (0.0-1.0) — your confidence in the forecast "
+    f"    given available data quality"
 ),
 expected_output=(
-    "A structured forecast with time slots, volumes, "
-    "required agents, and confidence score."
+    "Return a JSON object containing: forecast_period (string), "
+    "slots (list of objects with start_time, end_time, "
+    "predicted_volume, required_agents), total_predicted_volume "
+    "(integer), and confidence_score (float between 0 and 1)."
 ),
```

---

### 3. Leave Analyzer

#### [MODIFY] [leave_analyzer.py](file:///c:/Github%20Projects/crew-ai-hackathon-sama3a/backend/agents/leave_analyzer.py)

**Agent definition (lines 26–41)**

```diff
 role="Leave Analyzer",
 goal=(
-    "Analyze agent leave balances and schedules to detect overlapping "
-    "absences, assess coverage gaps, and compute schedule intersections "
-    "between pairs of agents to support shift swap decisions."
+    "Analyze approved and pending leave records for a queue, detect every "
+    "pair of agents whose absences overlap in time, compute the daily "
+    "coverage ratio (available agents / total agents), flag dates where "
+    "coverage drops below 85%, and classify each overlap and gap by "
+    "severity: low (>80% coverage), medium (60-80%), critical (<60%)."
 ),
 backstory=(
-    "You are a workforce planning analyst specializing in absence "
-    "management. You can quickly identify when simultaneous leaves "
-    "create coverage risks and evaluate whether shift swaps between "
-    "specific agents are feasible given their schedules."
+    "You are a BPO workforce planner specialized in absence-risk "
+    "analysis. You treat every overlapping leave as a potential "
+    "coverage risk and quantify the impact using the coverage-ratio "
+    "formula: (total_agents - absent_agents) / total_agents. You "
+    "always report severity classifications alongside raw numbers."
 ),
```

**Task description (lines 100–119)**

```diff
 description=(
-    f"Analyze leave data for queue '{state.queue_id}' "
-    f"during period '{state.time_window}'.\n\n"
-    f"Team context: {perf_context}\n"
-    f"Leave data from HR/Zendesk: {leave_context}\n\n"
-    f"Perform the following analysis:\n"
-    f"1. List all upcoming annual and sick leaves per agent\n"
-    f"2. Detect OVERLAPPING ABSENCES — date ranges where 2+ agents "
-    f"   in the same queue are simultaneously on leave\n"
-    f"3. Compute per-day COVERAGE RATIO and flag critical gaps\n"
-    f"4. For each pair of agents with overlapping leave, compute "
-    f"   their SCHEDULE INTERSECTION (shared shifts, shared leave days)\n"
-    f"5. Classify overlap severity: low (>80% coverage), "
-    f"   medium (60-80%), critical (<60%)"
+    f"Analyze leave records for queue '{state.queue_id}' during "
+    f"'{state.time_window}'.\n\n"
+    f"Team context: {perf_context}\n"
+    f"Leave data (from HR/Zendesk):\n{leave_context}\n\n"
+    f"Complete these steps in order:\n\n"
+    f"Step 1 — Agent leave inventory: For each record, extract "
+    f"agent_id, agent_name, leave_type (annual or sick), start_date, "
+    f"end_date, remaining_balance_days, and status.\n\n"
+    f"Step 2 — Overlap detection: Compare every pair of agents. "
+    f"When agent A's [start_date, end_date] intersects agent B's "
+    f"[start_date, end_date], record agent_a_id, agent_b_id, "
+    f"overlap_start, overlap_end, the affected queue, and severity "
+    f"(low: 1 day overlap, medium: 2-3 days, critical: 4+ days).\n\n"
+    f"Step 3 — Coverage gaps: For each calendar day in the leave "
+    f"window, count absent agents and compute coverage_ratio = "
+    f"(total_agents - absent) / total_agents. Flag every day where "
+    f"coverage_ratio < 0.85 and classify severity: low (>=0.80), "
+    f"medium (>=0.60), critical (<0.60)."
 ),
 expected_output=(
-    "A structured leave report with: agent leave list, "
-    "detected overlaps with severity, coverage gaps by date, "
-    "and schedule intersection data for overlapping pairs."
+    "Return a JSON object with: report_period (string), "
+    "agent_leaves (list of leave records), overlaps (list of "
+    "overlap objects with agent IDs, dates, queue, severity), "
+    "and coverage_gaps (list of objects with date, queue_id, "
+    "available_agents, required_agents, gap_severity)."
 ),
```

---

### 4. Performance-Aware Scheduler

#### [MODIFY] [perf_aware_scheduler.py](file:///c:/Github%20Projects/crew-ai-hackathon-sama3a/backend/agents/perf_aware_scheduler.py)

**Agent definition (lines 25–40)**

```diff
 role="Performance-Aware Scheduler",
 goal=(
-    "Generate optimized shift schedules that match agent strengths "
-    "to demand peaks while respecting leave constraints and maintaining "
-    "adequate coverage across all time slots."
+    "Generate an optimized shift schedule that assigns each available "
+    "agent to a specific shift window, matching agent strengths to "
+    "peak-demand slots, ensuring zero overlap with approved leave dates, "
+    "and achieving a coverage_score of at least 0.90. Include a clear "
+    "reason for every assignment."
 ),
 backstory=(
-    "You are a workforce optimization specialist who creates schedules "
-    "that balance employee well-being with operational efficiency. "
-    "You factor in skills, performance data, leave constraints, and "
-    "predicted demand to create the best possible shift assignments."
+    "You are a workforce optimization specialist for BPO operations "
+    "with expertise in constraint-based scheduling. You balance three "
+    "priorities: (1) skill-to-demand alignment — place high-FCR agents "
+    "on high-volume slots; (2) leave-respect — never assign an agent "
+    "during approved leave; (3) fairness — distribute shifts evenly "
+    "and avoid back-to-back shifts without a minimum 8-hour rest gap."
 ),
```

**Task description (lines 102–119) — mostly fine, minor refinements:**

```diff
 description=(
     f"Generate an optimized shift schedule for queue '{state.queue_id}' "
     f"during '{state.time_window}'.\n\n"
     f"Performance data: {perf_context}\n"
     f"Demand forecast: {forecast_context}\n"
     f"Leave constraints: {leave_context}\n\n"
-    f"Requirements:\n"
-    f"1. Assign EXACT Agent IDs from the 'Agent Details' provided above. DO NOT invent or mock agent IDs (e.g. no AGENT_001).\n"
-    f"2. Assign agents to shifts matching their strengths to peak demand\n"
-    f"3. Respect all approved leave dates — never schedule an agent on leave\n"
-    f"4. Avoid scheduling overlapping-leave gaps without backup coverage\n"
-    f"5. Optimize for coverage score (target > 0.90)\n"
-    f"6. Include reason for each assignment"
+    f"Scheduling rules (follow strictly):\n"
+    f"1. Use ONLY the exact Agent IDs listed in 'Agent Details' above.\n"
+    f"2. Match each agent's strengths to the slot with highest demand for "
+    f"   that skill.\n"
+    f"3. Verify each agent is available on the assigned date — skip any "
+    f"   agent whose approved leave covers that date.\n"
+    f"4. Ensure every time slot has at least the number of agents specified "
+    f"   by the demand forecast's required_agents.\n"
+    f"5. Target an overall coverage_score above 0.90.\n"
+    f"6. Write a one-sentence 'reason' for each assignment explaining why "
+    f"   this agent was chosen for this slot."
 ),
 expected_output=(
-    "A shift schedule with per-agent assignments, coverage score, "
-    "and explanatory notes. MUST only contain real Agent IDs."
+    "Return a JSON object containing: schedule_period (string), "
+    "assignments (list of objects with agent_id, shift_start, "
+    "shift_end, assigned_queue, reason), coverage_score (float "
+    "between 0 and 1), and notes (summary string). Use only real "
+    "Agent IDs from the provided data."
 ),
```

---

### 5. Shift Swap Coordinator

#### [MODIFY] [shift_swap_coordinator.py](file:///c:/Github%20Projects/crew-ai-hackathon-sama3a/backend/agents/shift_swap_coordinator.py)

**Agent definition (lines 26–41)**

```diff
 role="Shift Swap Coordinator",
 goal=(
-    "Evaluate proposed shift swaps between two agents by analyzing "
-    "their schedule intersection, leave conflicts, and impact on "
-    "overall queue coverage and team skill balance."
+    "Evaluate a proposed shift swap between two agents by checking "
+    "leave conflicts, computing their schedule intersection "
+    "(shared shift dates, shared leave dates, overlapping availability), "
+    "assessing coverage impact, identifying risk flags, and delivering "
+    "a clear feasible/infeasible verdict with a written recommendation."
 ),
 backstory=(
-    "You are a scheduling operations expert who evaluates shift swap "
-    "requests. You understand that a valid swap requires both agents "
-    "to be available, qualified, and that the swap must not create "
-    "coverage gaps or skill mismatches."
+    "You are a BPO scheduling operations expert. You evaluate every "
+    "swap against four criteria: (1) neither agent is on approved "
+    "leave on the swap date, (2) both agents meet a minimum 8-hour "
+    "rest period before and after the swapped shift, (3) neither "
+    "agent exceeds 48 weekly hours post-swap, and (4) the swap "
+    "maintains or improves the queue's coverage score."
 ),
```

**Task description (lines 80–96)**

```diff
 description=(
-    f"Analyze shift swap request between {swap.agent_a_id} and {swap.agent_b_id} "
-    f"for date '{swap.shift_date}'.\n\n"
-    f"Leave constraints: {leave_context}\n\n"
-    f"Perform the following:\n"
-    f"1. Check if either agent is on approved leave during the swap date\n"
-    f"2. Ensure the swap doesn't violate minimum rest periods\n"
-    f"3. Verify neither agent exceeds maximum weekly hours (mock check)\n"
-    f"4. Assess impact on coverage score — does it create gaps?\n"
-    f"5. Make a final feasibility verdict (True/False) with recommendations"
+    f"Evaluate this shift swap request:\n"
+    f"  • Agent A: {swap.agent_a_id} (shift: {swap.shift_a_id})\n"
+    f"  • Agent B: {swap.agent_b_id} (shift: {swap.shift_b_id})\n"
+    f"  • Swap date: {swap.shift_date}\n"
+    f"  • Reason: {swap.reason}\n\n"
+    f"Leave constraints: {leave_context}\n\n"
+    f"Complete these checks in order:\n"
+    f"  1. Leave conflict check: Confirm neither agent has approved leave "
+    f"     covering {swap.shift_date}. If either does, set feasible=False.\n"
+    f"  2. Rest-period check: Verify both agents have at least 8 hours "
+    f"     of rest before and after the swapped shift.\n"
+    f"  3. Weekly-hours check: Confirm neither agent would exceed 48 "
+    f"     weekly hours after the swap.\n"
+    f"  4. Coverage-impact assessment: Determine whether the swap "
+    f"     maintains or improves the queue's coverage score.\n"
+    f"  5. Produce a schedule intersection: list shared_shift_dates, "
+    f"     shared_leave_dates, and overlapping_availability_windows "
+    f"     between the two agents.\n"
+    f"  6. List any risk_flags (e.g., 'Agent A already at 44 weekly hours').\n"
+    f"  7. Set feasible=True or feasible=False and write a one-paragraph "
+    f"     recommendation."
 ),
 expected_output=(
-    "A structured swap analysis with: feasibility verdict, "
-    "schedule intersection details, coverage impact assessment, "
-    "risk flags, and a recommendation."
+    "Return a JSON object with: feasible (boolean), "
+    "agent_a_schedule_summary, agent_b_schedule_summary, "
+    "intersection (object with shared_shift_dates, shared_leave_dates, "
+    "overlapping_availability_windows, swap_compatible), "
+    "coverage_impact (string), risk_flags (list of strings), "
+    "and recommendation (string)."
 ),
```

---

### 6. Trainer Designer

#### [MODIFY] [trainer_designer.py](file:///c:/Github%20Projects/crew-ai-hackathon-sama3a/backend/agents/trainer_designer.py)

**Agent definition (lines 25–39)**

```diff
 role="Training Plan Designer",
 goal=(
-    "Analyze agent performance data to identify skill gaps and design "
-    "personalized, targeted training plans that improve underperforming "
-    "metrics while building on existing strengths."
+    "Review each agent's performance metrics (CSAT, FCR, escalation "
+    "rate), identify specific skill gaps, and design a personalized "
+    "training recommendation per agent that includes the gap name, "
+    "recommended training modules, estimated hours, and priority "
+    "(low / medium / high / critical). Also rank the top 3 agents "
+    "who need the most immediate training intervention."
 ),
 backstory=(
-    "You are a learning & development specialist who creates effective, "
-    "data-driven training programs for BPO teams. You know which training "
-    "modules map to which skill gaps and can estimate realistic timelines."
+    "You are a learning & development specialist with deep BPO "
+    "domain knowledge. You maintain a mental catalog of training "
+    "modules (e.g., 'Active Listening Workshop — 4 hrs', "
+    "'Product Refresher — 2 hrs', 'De-escalation Techniques — 3 hrs', "
+    "'CRM Advanced Features — 2 hrs') and map each module to the "
+    "metric it improves. You always set realistic hour estimates and "
+    "assign priority based on how far the agent's score is from the "
+    "team benchmark."
 ),
```

**Task description (lines 74–91)**

```diff
 description=(
-    f"Design a targeted training plan for queue '{state.queue_id}' "
-    f"during '{state.time_window}'.\n\n"
-    f"Team Analysis:\n{perf_context}\n\n"
-    f"For each agent showing performance gaps:\n"
-    f"1. Identify the specific skill gap (e.g., FCR, empathy, product knowledge)\n"
-    f"2. Recommend relevant training modules\n"
-    f"3. Estimate required hours for completion\n"
-    f"4. Assign priority (low/medium/high/critical)\n\n"
-    f"REQUIREMENT: You MUST ONLY use the exact Agent IDs provided in the Team Analysis above. Do not invent or mock new agents.\n"
-    f"Also identify the top 3 PRIORITY AGENTS who need the most "
-    f"immediate attention."
+    f"Design a training plan for queue '{state.queue_id}' covering "
+    f"'{state.time_window}'.\n\n"
+    f"Agent performance data:\n{perf_context}\n\n"
+    f"Step 1 — Gap analysis: For each agent listed above, compare "
+    f"their CSAT, FCR, and escalation_rate to the team average. Flag "
+    f"any metric where the agent is >10% worse than the team mean.\n\n"
+    f"Step 2 — Training recommendations: For each flagged agent, "
+    f"produce:\n"
+    f"  a. agent_id — use ONLY the exact IDs from the data above\n"
+    f"  b. skill_gaps — list of identified gap names (e.g., "
+    f"     'low FCR', 'high escalation rate', 'poor product knowledge')\n"
+    f"  c. recommended_modules — list of training module names that "
+    f"     address these gaps\n"
+    f"  d. estimated_hours — total hours across all modules\n"
+    f"  e. priority — 'critical' if any metric is >25% below team avg, "
+    f"     'high' if >15%, 'medium' if >10%, 'low' otherwise\n\n"
+    f"Step 3 — Priority ranking: List the top 3 agent_ids who need "
+    f"the most urgent training, ordered by severity of gaps."
 ),
 expected_output=(
-    "A training plan with per-agent recommendations, "
-    "including skill gaps, modules, hours, and priority. MUST only contain real Agent IDs."
+    "Return a JSON object with: plan_period (string), "
+    "recommendations (list of objects with agent_id, skill_gaps, "
+    "recommended_modules, estimated_hours, priority), and "
+    "priority_agents (list of the top 3 agent IDs). Use only "
+    "real Agent IDs from the provided data."
 ),
```

## Verification Plan

### Manual Verification

Since these are LLM prompt changes with no structural code modifications, the primary way to verify is:

1. **Run the existing integration test** to ensure nothing breaks structurally:
   ```
   cd c:\Github Projects\crew-ai-hackathon-sama3a
   python test_flow.py
   ```
   This requires the backend server to be running (`uvicorn main:app`).

2. **Inspect output quality**: After running the flow, check the API response at `/api/flow/{run_id}/state` and verify that agent outputs are more detailed, contain correct field names, and align with the Pydantic schemas.

> [!IMPORTANT]
> Since these are prompt-only changes (no Python logic changes), the risk of breaking the code is very low. The prompts are only modifying string literals inside `Agent()` and `Task()` definitions.
