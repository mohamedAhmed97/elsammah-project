/**
 * BPO Ops Superflow — TypeScript Type Definitions
 *
 * Mirrors the backend Pydantic models for type-safe communication
 * between the React frontend and FastAPI backend.
 */

// ---------------------------------------------------------------------------
// Enum Types
// ---------------------------------------------------------------------------
export type FlowType = "training" | "schedule" | "hybrid" | "leave_review" | "shift_swap";
export type HITLStatus = "not_required" | "pending" | "approved" | "rejected" | "edited";
export type HITLDecisionType = "approve" | "reject" | "edit";
export type LeaveType = "annual" | "sick";
export type LeaveStatus = "approved" | "pending" | "rejected";
export type Severity = "low" | "medium" | "critical";
export type TrainingPriority = "low" | "medium" | "high" | "critical";

// ---------------------------------------------------------------------------
// Agent Performance
// ---------------------------------------------------------------------------
export interface AgentPerf {
    agent_id: string;
    agent_name: string;
    avg_handle_time_seconds: number;
    csat_score: number;
    fcr_rate: number;
    escalation_rate: number;
    schedule_adherence: number;
    strengths: string[];
    gaps: string[];
}

export interface TeamPerfMetrics {
    agents: AgentPerf[];
    team_avg_handle_time: number;
    team_avg_csat: number;
    team_avg_fcr: number;
    computed_at: string;
}

// ---------------------------------------------------------------------------
// Demand Forecast
// ---------------------------------------------------------------------------
export interface TimeSlot {
    start_time: string;
    end_time: string;
    predicted_volume: number;
    required_agents: number;
}

export interface DemandForecast {
    forecast_period: string;
    slots: TimeSlot[];
    total_predicted_volume: number;
}

// ---------------------------------------------------------------------------
// Leave Analysis
// ---------------------------------------------------------------------------
export interface AgentLeave {
    agent_id: string;
    agent_name: string;
    leave_type: LeaveType;
    start_date: string;
    end_date: string;
    remaining_balance_days: number;
    status: LeaveStatus;
}

export interface LeaveOverlap {
    agent_a_id: string;
    agent_b_id: string;
    overlap_start: string;
    overlap_end: string;
    affected_queue: string;
    severity: Severity;
}

export interface CoverageGap {
    date: string;
    queue_id: string;
    available_agents: number;
    required_agents: number;
    gap_severity: Severity;
}

export interface LeaveReport {
    report_period: string;
    agent_leaves: AgentLeave[];
    overlaps: LeaveOverlap[];
    coverage_gaps: CoverageGap[];
}

// ---------------------------------------------------------------------------
// Schedule
// ---------------------------------------------------------------------------
export interface ShiftAssignment {
    agent_id: string;
    shift_start: string;
    shift_end: string;
    assigned_queue: string;
    reason: string;
}

export interface ScheduleOutput {
    schedule_period: string;
    assignments: ShiftAssignment[];
    coverage_score: number;
    notes: string;
}

// ---------------------------------------------------------------------------
// Shift Swap
// ---------------------------------------------------------------------------
export interface SwapRequest {
    agent_a_id: string;
    agent_b_id: string;
    shift_date: string;
    shift_a_id: string;
    shift_b_id: string;
    reason: string;
}

export interface ScheduleIntersection {
    shared_shift_dates: string[];
    shared_leave_dates: string[];
    overlapping_availability_windows: TimeSlot[];
    swap_compatible: boolean;
}

export interface ShiftSwapResult {
    feasible: boolean;
    agent_a_schedule_summary: string;
    agent_b_schedule_summary: string;
    intersection: ScheduleIntersection;
    coverage_impact: string;
    risk_flags: string[];
    recommendation: string;
}

// ---------------------------------------------------------------------------
// Training Plan
// ---------------------------------------------------------------------------
export interface TrainingRecommendation {
    agent_id: string;
    skill_gaps: string[];
    recommended_modules: string[];
    estimated_hours: number;
    priority: TrainingPriority;
}

export interface TrainingPlan {
    plan_period: string;
    recommendations: TrainingRecommendation[];
    priority_agents: string[];
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------
export interface RedactedTranscript {
    transcript_id: string;
    queue_id: string;
    agent_id: string;
    content: string;
    duration_seconds: number;
    timestamp: string;
    metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// HITL
// ---------------------------------------------------------------------------
export interface HITLDecision {
    decision: HITLDecisionType;
    reviewer_id: string;
    comments: string;
    edits?: Record<string, unknown>;
    decided_at: string;
}

// ---------------------------------------------------------------------------
// Observability
// ---------------------------------------------------------------------------
export interface AuditLogEntry {
    timestamp: string;
    step_name: string;
    event_type: string;
    message: string;
    data?: Record<string, unknown>;
}

export interface ErrorDetail {
    step_name: string;
    error_type: string;
    message: string;
    recoverable: boolean;
}

// ---------------------------------------------------------------------------
// API Request / Response
// ---------------------------------------------------------------------------
export interface FlowStartRequest {
    flow_type: FlowType;
    queue_id: string;
    time_window: string;
    swap_request?: SwapRequest;
}

export interface FlowStartResponse {
    run_id: string;
    status: string;
}

export interface FlowRunSummary {
    run_id: string;
    flow_type: FlowType;
    queue_id: string;
    time_window: string;
    status: string;
    created_at: string;
}

export interface HITLDecisionRequest {
    decision: HITLDecisionType;
    reviewer_id: string;
    comments: string;
    edits?: Record<string, unknown>;
}

export interface HITLDecisionResponse {
    status: string;
    run_id: string;
}

export interface APIError {
    error_type: string;
    message: string;
    details?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Flow State
// ---------------------------------------------------------------------------
export interface BPOFlowState {
    run_id: string;
    created_at: string;
    flow_type: FlowType;
    time_window: string;
    queue_id: string;
    swap_request?: SwapRequest;
    transcripts: RedactedTranscript[];
    team_perf?: TeamPerfMetrics;
    demand_forecast?: DemandForecast;
    leave_report?: LeaveReport;
    schedule_output?: ScheduleOutput;
    training_plan?: TrainingPlan;
    swap_result?: ShiftSwapResult;
    hitl_status: HITLStatus;
    hitl_decision?: HITLDecision;
    current_step: string;
    audit_log: AuditLogEntry[];
    error_state?: ErrorDetail;
}

// ---------------------------------------------------------------------------
// SSE Event
// ---------------------------------------------------------------------------
export type SSEEventType =
    | "step_started"
    | "step_completed"
    | "hitl_required"
    | "hitl_resolved"
    | "flow_completed"
    | "flow_error"
    | "leave_overlap_detected"
    | "swap_feasibility";

export interface SSEEvent {
    event: SSEEventType;
    data: {
        run_id: string;
        timestamp: string;
        step?: string;
        message?: string;
        payload?: Record<string, unknown>;
    };
}
