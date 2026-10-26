import { useState } from "react";
import type { FlowStartRequest, FlowType } from "../types";

interface RunFormProps {
    onSubmit: (request: FlowStartRequest) => void;
    disabled: boolean;
}

const FLOW_TYPES: { value: FlowType; label: string; description: string; icon: string }[] = [
    { value: "schedule", label: "Schedule", description: "Generate optimized shift schedules", icon: "calendar_month" },
    { value: "training", label: "Training", description: "Design targeted training plans", icon: "school" },
    { value: "hybrid", label: "Hybrid", description: "Both schedule + training", icon: "hub" },
    { value: "leave_review", label: "Leave", description: "Analyze leave gaps", icon: "event_busy" },
    { value: "shift_swap", label: "Swap", description: "Evaluate swap requests", icon: "sync_alt" },
];

export default function RunForm({ onSubmit, disabled }: RunFormProps) {
    const [flowType, setFlowType] = useState<FlowType>("hybrid");
    const [queueId, setQueueId] = useState("Q-SUPPORT-01");
    const [timeWindow, setTimeWindow] = useState("2025-W24");

    // Swap-specific fields
    const [agentAId, setAgentAId] = useState("AGT-201");
    const [agentBId, setAgentBId] = useState("AGT-202");
    const [shiftDate, setShiftDate] = useState("2025-06-18");
    const [swapReason, setSwapReason] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const request: FlowStartRequest = {
            flow_type: flowType,
            queue_id: queueId,
            time_window: timeWindow,
        };

        if (flowType === "shift_swap") {
            request.swap_request = {
                agent_a_id: agentAId,
                agent_b_id: agentBId,
                shift_date: shiftDate,
                shift_a_id: `SHIFT-${agentAId}`,
                shift_b_id: `SHIFT-${agentBId}`,
                reason: swapReason,
            };
        }

        onSubmit(request);
    };

    return (
        <div className="glass-panel p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
            {/* Decorative element */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-accent-blue/5 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>

            <form onSubmit={handleSubmit} className="relative z-10 space-y-5">
                <div className="flex items-center gap-2 mb-2">
                    <span className="material-symbols-outlined text-accent-blue text-xl">play_arrow</span>
                    <h2 className="text-lg font-bold text-text-dark dark:text-white">New Execution</h2>
                </div>

                {/* Flow Type Selector */}
                <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                        Operation Type
                    </label>
                    <div className="grid grid-cols-1 gap-2">
                        {FLOW_TYPES.map((ft) => (
                            <button
                                key={ft.value}
                                type="button"
                                onClick={() => setFlowType(ft.value)}
                                disabled={disabled}
                                className={`flex items-start gap-3 px-3 py-2.5 rounded-xl text-left transition-all border ${flowType === ft.value
                                    ? "bg-accent-blue/10 border-accent-blue/50 ring-1 ring-accent-blue/30 text-accent-blue dark:text-blue-300"
                                    : "bg-white/50 dark:bg-slate-800/30 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                                    } disabled:opacity-50`}
                            >
                                <span className="material-symbols-outlined text-[18px] mt-0.5">{ft.icon}</span>
                                <div>
                                    <span className="block font-bold text-sm leading-tight text-text-dark dark:text-white">{ft.label}</span>
                                    <span className="block text-[10px] font-medium opacity-80 mt-0.5">{ft.description}</span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Queue ID & Time Window */}
                <div className="flex flex-col gap-3">
                    <div>
                        <label htmlFor="queue-id" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                            Queue ID
                        </label>
                        <input
                            id="queue-id"
                            type="text"
                            value={queueId}
                            onChange={(e) => setQueueId(e.target.value)}
                            disabled={disabled}
                            className="w-full px-3 py-2 rounded-lg bg-white/70 dark:bg-slate-900/50 text-text-dark dark:text-white border border-slate-200 dark:border-slate-700 focus:border-accent-blue focus:ring-1 focus:ring-accent-blue text-sm disabled:opacity-50 transition-colors shadow-sm"
                            placeholder="Q-SUPPORT-01"
                        />
                    </div>
                    <div>
                        <label htmlFor="time-window" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                            Time Window
                        </label>
                        <input
                            id="time-window"
                            type="text"
                            value={timeWindow}
                            onChange={(e) => setTimeWindow(e.target.value)}
                            disabled={disabled}
                            className="w-full px-3 py-2 rounded-lg bg-white/70 dark:bg-slate-900/50 text-text-dark dark:text-white border border-slate-200 dark:border-slate-700 focus:border-accent-blue focus:ring-1 focus:ring-accent-blue text-sm disabled:opacity-50 transition-colors shadow-sm"
                            placeholder="2025-W24"
                        />
                    </div>
                </div>

                {/* Swap-specific fields */}
                {flowType === "shift_swap" && (
                    <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-primary">
                            Swap Details
                        </p>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label htmlFor="agent-a" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Agent A</label>
                                <input
                                    id="agent-a"
                                    type="text"
                                    value={agentAId}
                                    onChange={(e) => setAgentAId(e.target.value)}
                                    disabled={disabled}
                                    className="w-full px-3 py-1.5 rounded-lg bg-white/70 dark:bg-slate-900/50 text-text-dark dark:text-white border border-slate-200 dark:border-slate-700 text-sm disabled:opacity-50 shadow-sm"
                                />
                            </div>
                            <div>
                                <label htmlFor="agent-b" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Agent B</label>
                                <input
                                    id="agent-b"
                                    type="text"
                                    value={agentBId}
                                    onChange={(e) => setAgentBId(e.target.value)}
                                    disabled={disabled}
                                    className="w-full px-3 py-1.5 rounded-lg bg-white/70 dark:bg-slate-900/50 text-text-dark dark:text-white border border-slate-200 dark:border-slate-700 text-sm disabled:opacity-50 shadow-sm"
                                />
                            </div>
                        </div>
                        <div>
                            <label htmlFor="shift-date" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Shift Date</label>
                            <input
                                id="shift-date"
                                type="date"
                                value={shiftDate}
                                onChange={(e) => setShiftDate(e.target.value)}
                                disabled={disabled}
                                className="w-full px-3 py-1.5 rounded-lg bg-white/70 dark:bg-slate-900/50 text-text-dark dark:text-white border border-slate-200 dark:border-slate-700 text-sm disabled:opacity-50 shadow-sm color-scheme-light dark:color-scheme-dark"
                            />
                        </div>
                        <div>
                            <label htmlFor="swap-reason" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Reason</label>
                            <input
                                id="swap-reason"
                                type="text"
                                value={swapReason}
                                onChange={(e) => setSwapReason(e.target.value)}
                                disabled={disabled}
                                className="w-full px-3 py-1.5 rounded-lg bg-white/70 dark:bg-slate-900/50 text-text-dark dark:text-white border border-slate-200 dark:border-slate-700 text-sm disabled:opacity-50 shadow-sm"
                                placeholder="Personal request..."
                            />
                        </div>
                    </div>
                )}

                {/* Submit */}
                <button
                    type="submit"
                    disabled={disabled || !queueId || !timeWindow}
                    className="w-full py-3 rounded-xl bg-accent-blue text-white font-bold text-sm shadow-md hover:bg-blue-700 hover:shadow-lg transition-all active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100 disabled:cursor-not-allowed flex justify-center items-center gap-2 mt-4"
                >
                    {disabled ? (
                        <>
                            <svg className="animate-spin h-5 w-5 shrink-0 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <span>Executing...</span>
                        </>
                    ) : (
                        <>
                            <span className="material-symbols-outlined text-[18px]">rocket_launch</span>
                            Initialize Pipeline
                        </>
                    )}
                </button>
            </form>
        </div>
    );
}
