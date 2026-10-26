import { useEffect, useRef } from "react";
import type { AuditLogEntry, FlowType } from "../types";

interface LiveConsoleProps {
    entries: AuditLogEntry[];
    currentStep: string;
    flowType?: FlowType;
}

const EVENT_COLORS: Record<string, string> = {
    step_started: "text-blue-500 dark:text-blue-400",
    step_completed: "text-emerald-500 dark:text-emerald-400",
    step_skipped: "text-slate-400",
    routing: "text-purple-500 dark:text-purple-400",
    hitl_required: "text-amber-500",
    hitl_resolved: "text-amber-600 dark:text-amber-400",
    flow_completed: "text-green-600 dark:text-green-500",
    flow_error: "text-red-500",
    error: "text-red-500",
};

const EVENT_ICONS: Record<string, string> = {
    step_started: "play_circle",
    step_completed: "check_circle",
    step_skipped: "skip_next",
    routing: "route",
    hitl_required: "front_hand",
    hitl_resolved: "how_to_reg",
    flow_completed: "task_alt",
    flow_error: "error",
    error: "error",
};

export default function LiveConsole({ entries, currentStep }: LiveConsoleProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [entries]);

    return (
        <div className="glass-panel rounded-2xl border border-slate-200 dark:border-slate-800 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] flex flex-col h-full overflow-hidden relative">
            <div className="flex items-center justify-between p-4 bg-white/50 dark:bg-slate-900/50 z-10 relative border-b border-slate-200 dark:border-slate-800">
                <h2 className="text-[11px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                    <span className="material-symbols-outlined text-[16px] text-accent-blue bg-accent-blue/10 rounded p-0.5">terminal</span>
                    Live Audit Log
                </h2>
                {currentStep && (
                    <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-full shadow-inner">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
                        {currentStep}
                    </span>
                )}
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-5 font-mono text-xs space-y-4 bg-white/30 dark:bg-[#070B14]/60 scrollbar-hide relative z-0 shadow-inner"
            >
                {entries.filter(e => e.event_type !== "step_skipped").length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400 dark:text-slate-500 font-medium pt-8">
                        <span className="material-symbols-outlined text-3xl mb-2 opacity-30">hourglass_empty</span>
                        <p>Waiting for pipeline events...</p>
                    </div>
                ) : (
                    entries.filter(e => e.event_type !== "step_skipped").map((entry, i) => {
                        const colorClass = EVENT_COLORS[entry.event_type] ?? "text-slate-500 dark:text-slate-400";
                        const iconLiteral = EVENT_ICONS[entry.event_type] ?? "radio_button_unchecked";
                        const time = new Date(entry.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 });

                        return (
                            <div key={i} className="flex gap-3 group relative transition-colors hover:bg-slate-100/50 dark:hover:bg-slate-800/50 rounded -mx-2 px-2 py-1">
                                <span className="text-slate-400 dark:text-slate-500 shrink-0 w-24 tabular-nums opacity-60 group-hover:opacity-100 transition-opacity flex items-center">{time}</span>
                                <span className={`shrink-0 flex justify-center items-start mt-0.5 ${colorClass}`}>
                                    <span className="material-symbols-outlined text-[16px]">{iconLiteral}</span>
                                </span>
                                <div className="flex flex-col gap-0.5 w-full">
                                    <span className="font-bold text-slate-700 dark:text-slate-300">[{entry.step_name}]</span>
                                    <span className="text-slate-600 dark:text-slate-400 leading-relaxed max-w-[95%]">{entry.message}</span>
                                </div>
                            </div>
                        );
                    })
                )}
                {/* Extra padding at bottom to ensure last item is fully visible */}
                <div className="h-4"></div>
            </div>
        </div>
    );
}
