import type { BPOFlowState, TimeSlot } from "../types";

interface ResultsPanelProps {
    flowState: BPOFlowState | null;
    isRunning: boolean;
    currentStep?: string;
}

export default function ResultsPanel({ flowState, isRunning, currentStep }: ResultsPanelProps) {
    if (!flowState) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 dark:text-slate-500 font-medium">
                <span className="material-symbols-outlined text-4xl mb-4 opacity-50">analytics</span>
                <p>System idle. Waiting for pipeline execution.</p>
            </div>
        );
    }

    if (isRunning && !flowState.hitl_status?.match(/approved|rejected|edited/)) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-accent-blue dark:text-blue-400 font-medium">
                <div className="relative w-16 h-16 flex items-center justify-center mb-4">
                    <svg className="animate-spin text-accent-blue dark:text-blue-500 w-12 h-12" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </div>
                <p className="animate-pulse flex items-center gap-2">
                    Processing Pipeline: <span className="font-bold">{currentStep || "Initializing..."}</span>
                </p>
            </div>
        );
    }

    const hasResults =
        flowState.team_perf ||
        flowState.demand_forecast ||
        flowState.schedule_output ||
        flowState.training_plan ||
        flowState.leave_report ||
        flowState.swap_result;

    if (!hasResults) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 font-medium italic">
                <span className="material-symbols-outlined text-3xl mb-2 opacity-30">warning</span>
                Flow completed but no structured outputs were generated.
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto pr-2 scrollbar-hide space-y-6">
            <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-bold text-text-dark dark:text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-accent-blue bg-accent-blue/10 p-1 rounded">deployed_code</span>
                    Execution Results
                </h3>

                {flowState.hitl_status && flowState.hitl_status !== "not_required" && (
                    <div className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider shadow-sm flex items-center gap-1.5 ${flowState.hitl_status === "approved"
                        ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 border border-green-200 dark:border-green-800"
                        : flowState.hitl_status === "rejected"
                            ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border border-red-200 dark:border-red-800"
                            : flowState.hitl_status === "edited"
                                ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
                                : "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 border border-blue-200 dark:border-blue-800"
                        }`}>
                        <span className={`w-2 h-2 rounded-full ${flowState.hitl_status === "approved" ? "bg-green-500" :
                            flowState.hitl_status === "rejected" ? "bg-red-500" :
                                flowState.hitl_status === "edited" ? "bg-amber-500" : "bg-blue-500"
                            }`}></span>
                        Decision: {flowState.hitl_status}
                        {flowState.hitl_decision?.reviewer_id && (
                            <span className="ml-1 opacity-75 hidden sm:inline-block border-l pl-2 border-inherit">by {flowState.hitl_decision.reviewer_id}</span>
                        )}
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Team Performance */}
                {flowState.team_perf && (
                    <ResultSection title="Team Performance" icon="monitoring">
                        <div className="flex flex-col gap-3 mb-2">
                            <MetricCard label="Avg Processing" value={`${flowState.team_perf.team_avg_handle_time.toFixed(1)}s`} />
                            <div className="grid grid-cols-2 gap-3">
                                <MetricCard label="CSAT Score" value={flowState.team_perf.team_avg_csat.toFixed(2)} />
                                <MetricCard label="FCR Rate" value={`${(flowState.team_perf.team_avg_fcr * 100).toFixed(0)}%`} />
                            </div>
                        </div>
                    </ResultSection>
                )}

                {/* Demand Forecast */}
                {flowState.demand_forecast && (
                    <ResultSection title="Demand Forecast" icon="trending_up">
                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <MetricCard label="Time Slots" value={flowState.demand_forecast.slots.length.toString()} />
                            <MetricCard label="Total Volume" value={flowState.demand_forecast.total_predicted_volume.toString()} />
                        </div>
                        {flowState.demand_forecast.slots.length > 0 && (
                            <div className="mt-3 space-y-2">
                                {flowState.demand_forecast.slots.slice(0, 3).map((slot: TimeSlot, i: number) => (
                                    <div key={i} className="flex justify-between items-center text-xs px-3 py-2 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700 shadow-sm transition-transform hover:scale-[1.02]">
                                        <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5"><span className="material-symbols-outlined text-[14px] text-slate-400">schedule</span>{slot.start_time} - {slot.end_time}</span>
                                        <span className="text-accent-blue dark:text-blue-400 font-bold bg-accent-blue/10 px-2 py-0.5 rounded">{slot.required_agents} agents</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </ResultSection>
                )}
            </div>

            {/* Schedule Output */}
            {flowState.schedule_output && (
                <ResultSection title="Generated Schedule" icon="calendar_month">
                    <div className="flex items-center justify-between text-sm mb-4">
                        <span className="text-slate-600 dark:text-slate-400 font-bold flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-green-500">check_circle</span> {flowState.schedule_output.assignments.length} assignments created</span>
                        {flowState.schedule_output.coverage_score != null && (
                            <span className="px-2.5 py-1 bg-primary/20 text-brand-dark dark:text-primary rounded-md text-[10px] uppercase font-bold tracking-wider">
                                Coverage Score: {(flowState.schedule_output.coverage_score * 100).toFixed(0)}%
                            </span>
                        )}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {flowState.schedule_output.assignments.map((a, i) => (
                            <div key={i} className="flex flex-col text-xs p-3 glass-panel rounded-xl shadow-sm hover:shadow-md transition-all">
                                <div className="flex justify-between items-center mb-2 pb-2 border-b border-slate-200 dark:border-slate-700">
                                    <span className="font-bold text-text-dark dark:text-white flex items-center gap-1"><span className="material-symbols-outlined text-[14px] text-slate-400">person</span>{a.agent_id}</span>
                                    <div className="flex items-center gap-1.5">
                                        {a.reason && <span title={a.reason} className="material-symbols-outlined text-[15px] text-accent-blue/80 hover:text-accent-blue dark:text-blue-500/80 dark:hover:text-blue-400 cursor-help transition-colors">info</span>}
                                        {a.assigned_queue && <span className="text-[9px] uppercase font-bold tracking-wider bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded">{a.assigned_queue}</span>}
                                    </div>
                                </div>
                                <span className="text-slate-500 dark:text-slate-400 font-medium flex justify-center items-center gap-2"><span className="material-symbols-outlined text-[12px]">schedule</span> {a.shift_start} - {a.shift_end}</span>
                            </div>
                        ))}
                    </div>
                </ResultSection>
            )}

            {/* Training Plan */}
            {flowState.training_plan && (
                <ResultSection title="Training Recommendations" icon="school">
                    {flowState.training_plan.priority_agents && flowState.training_plan.priority_agents.length > 0 && (
                        <div className="mb-4 px-4 py-3 bg-red-50/80 dark:bg-red-900/10 border border-red-200/60 dark:border-red-900/30 rounded-xl flex items-start gap-3 shadow-sm">
                            <span className="material-symbols-outlined text-red-500 dark:text-red-400 text-[20px] mt-0.5">emergency_home</span>
                            <div className="flex flex-col gap-0.5">
                                <span className="text-[10px] font-black uppercase tracking-widest text-red-600 dark:text-red-500">Critical Intervention Required</span>
                                <span className="text-sm font-bold text-red-700 dark:text-red-300">Agent IDs: {flowState.training_plan.priority_agents.join(", ")}</span>
                            </div>
                        </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {flowState.training_plan.recommendations.slice(0, 6).map((rec, i) => (
                            <div key={i} className="flex justify-between items-start p-3 bg-white/60 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm relative overflow-hidden group">
                                <div className={`absolute left-0 top-0 bottom-0 w-1 ${rec.priority === "high" ? "bg-red-500" :
                                    rec.priority === "medium" ? "bg-amber-500" : "bg-blue-500"
                                    }`}></div>

                                <div className="flex flex-col gap-1.5 pl-2 z-10 w-full">
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-bold text-text-dark dark:text-white flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-slate-400">person</span> {rec.agent_id}</span>
                                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full ${rec.priority === "high" || rec.priority === "critical" ? "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" :
                                            rec.priority === "medium" ? "bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400" :
                                                "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
                                            }`}
                                            title={
                                                rec.priority === 'critical' ? 'Urgent upskilling required immediately' :
                                                    rec.priority === 'high' ? 'High priority compliance training' :
                                                        rec.priority === 'medium' ? 'Standard performance improvement' :
                                                            'Low priority maintenance training'
                                            }
                                        >
                                            {rec.priority}
                                        </span>
                                    </div>
                                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-900/50 p-1.5 rounded inline-block w-fit mb-1">Target Skills: {rec.skill_gaps.join(", ")}</span>
                                    {rec.recommended_modules && rec.recommended_modules.length > 0 && (
                                        <div className="pt-2 mt-1 border-t border-slate-200/50 dark:border-slate-700/50 flex flex-col gap-1.5">
                                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Recommended Courses</span>
                                            <ul className="text-xs text-slate-600 dark:text-slate-300 list-disc pl-4 space-y-0.5 font-medium">
                                                {rec.recommended_modules.map((mod: string, midx: number) => (
                                                    <li key={midx}>{mod}</li>
                                                ))}
                                            </ul>
                                            <div className="flex items-center gap-1.5 mt-1 text-accent-blue dark:text-blue-400 text-[11px] font-bold bg-accent-blue/10 w-fit px-2 py-1 rounded">
                                                <span className="material-symbols-outlined text-[13px]">timer</span>
                                                {rec.estimated_hours} Hours Estimated
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </ResultSection>
            )}

            {/* Leave Report */}
            {flowState.leave_report && (
                <ResultSection title="Leave Analysis" icon="event_busy">
                    <div className="grid grid-cols-2 gap-3 mb-4">
                        <MetricCard label="Active Leaves" value={flowState.leave_report.agent_leaves.length.toString()} />
                        <MetricCard label="Schedule Overlaps" value={flowState.leave_report.overlaps.length.toString()} />
                    </div>
                    {flowState.leave_report.coverage_gaps.length > 0 && (
                        <div className="mt-3">
                            <h5 className="text-xs font-bold uppercase tracking-wider text-red-500 mb-2 flex items-center gap-1.5"><span className="material-symbols-outlined text-[14px]">warning</span> Critical Coverage Gaps</h5>
                            <div className="space-y-2">
                                {flowState.leave_report.coverage_gaps.slice(0, 4).map((gap, i) => (
                                    <div key={i} className="text-xs text-text-dark dark:text-slate-300 px-3 py-2 bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/30 rounded-lg flex justify-between items-center">
                                        <span className="font-bold">{gap.date}</span>
                                        <span className="">Avail: <strong className={gap.available_agents < gap.required_agents ? "text-red-600 dark:text-red-400" : ""}>{gap.available_agents}</strong> / Req: {gap.required_agents}</span>
                                        <span className="text-[10px] font-bold uppercase text-red-500 bg-red-100 dark:bg-red-950 px-1.5 py-0.5 rounded">{gap.gap_severity} SEVERITY</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </ResultSection>
            )}

            {/* Swap Result */}
            {flowState.swap_result && (
                <ResultSection title="Swap Evaluation" icon="sync_alt">
                    <div className={`px-4 py-3 rounded-xl border flex items-center gap-3 shadow-sm mb-3 ${flowState.swap_result.feasible
                        ? "bg-green-50/80 border-green-200 dark:bg-green-900/20 dark:border-green-800 text-green-700 dark:text-green-400"
                        : "bg-red-50/80 border-red-200 dark:bg-red-900/20 dark:border-red-800 text-red-700 dark:text-red-400"
                        }`}>
                        <span className="material-symbols-outlined text-2xl">
                            {flowState.swap_result.feasible ? "check_circle" : "cancel"}
                        </span>
                        <div className="flex flex-col">
                            <span className="text-sm font-bold uppercase tracking-wider">
                                {flowState.swap_result.feasible ? "SWAP FEASIBLE" : "SWAP NOT FEASIBLE"}
                            </span>
                        </div>
                    </div>

                    <div className="mb-3 flex flex-col gap-2">
                        <div className="px-4 py-3 bg-slate-50/80 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-700">
                            <span className="block text-[10px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 mb-1.5 flex items-center gap-1.5"><span className="material-symbols-outlined text-[14px]">psychology</span>Agent Recommendation</span>
                            <span className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-medium">{flowState.swap_result.recommendation}</span>
                        </div>
                        <div className="px-4 py-3 bg-slate-50/80 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-700">
                            <span className="block text-[10px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 mb-1.5 flex items-center gap-1.5"><span className="material-symbols-outlined text-[14px]">query_stats</span>Coverage Impact</span>
                            <span className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-medium">{flowState.swap_result.coverage_impact}</span>
                        </div>
                    </div>
                    {flowState.swap_result.risk_flags.length > 0 && (
                        <div className="space-y-1 mt-3">
                            <h5 className="text-[10px] font-bold uppercase tracking-wider text-amber-500 mb-1">Identified Risk Flags</h5>
                            {flowState.swap_result.risk_flags.map((flag, i) => (
                                <div key={i} className="text-xs text-amber-700 dark:text-amber-300 font-medium px-3 py-1.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-900/30 rounded flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                                    {flag}
                                </div>
                            ))}
                        </div>
                    )}
                </ResultSection>
            )}

        </div>
    );
}

function ResultSection({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
    return (
        <div className="glass-panel border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] relative overflow-hidden group">
            <h4 className="flex items-center gap-2 text-[11px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-4">
                <span className="material-symbols-outlined text-[16px] text-accent-blue bg-accent-blue/10 rounded p-0.5 group-hover:bg-accent-blue group-hover:text-white transition-colors">{icon}</span>
                {title}
            </h4>
            <div className="relative z-10">
                {children}
            </div>
        </div>
    );
}

function MetricCard({ label, value }: { label: string; value: string }) {
    return (
        <div className="bg-white/40 dark:bg-slate-800/40 rounded-xl p-2 sm:p-3 py-3 border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-center items-center text-center shadow-sm relative overflow-hidden group transition-all hover:bg-white/80 dark:hover:bg-slate-800">
            <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-transparent dark:from-white/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
            <div className="text-lg sm:text-xl lg:text-2xl font-black text-text-dark dark:text-white mb-1 group-hover:text-accent-blue dark:group-hover:text-blue-400 transition-colors tracking-tight">{value}</div>
            <div className="text-[8px] sm:text-[9px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 leading-tight">{label}</div>
        </div>
    );
}
