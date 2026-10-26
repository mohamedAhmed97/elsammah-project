import { useEffect, useState } from "react";
import type { FlowRunSummary } from "../types";

interface HistoryPanelProps {
    onSelectRun: (runId: string) => void;
}

export default function HistoryPanel({ onSelectRun }: HistoryPanelProps) {
    const [runs, setRuns] = useState<FlowRunSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const response = await fetch('/api/flow/history');
                if (!response.ok) {
                    throw new Error("Failed to fetch history");
                }
                const data = await response.json();
                setRuns(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "An error occurred");
            } finally {
                setIsLoading(false);
            }
        };

        fetchHistory();
    }, []);

    const getStatusToken = (status: string) => {
        switch (status) {
            case "approved":
                return <span className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md border border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400 flex items-center w-max gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-500"></span> Approved</span>;
            case "rejected":
                return <span className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400 flex items-center w-max gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> Rejected</span>;
            case "edited":
                return <span className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center w-max gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Edited</span>;
            case "not_required":
                return <span className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md border border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center w-max gap-1"><span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Auto-Finalized</span>;
            default:
                return <span className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md border border-slate-500/30 bg-slate-500/10 text-slate-600 dark:text-slate-400 flex items-center w-max gap-1"><span className="w-1.5 h-1.5 rounded-full bg-slate-500"></span> {status}</span>;
        }
    };

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400">
                <div className="relative w-12 h-12 flex items-center justify-center mb-4">
                    <svg className="animate-spin text-accent-blue dark:text-blue-500 w-10 h-10" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </div>
                <span className="font-medium animate-pulse">Loading execution history...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 rounded-xl bg-red-50/80 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm shadow-sm flex items-center gap-3">
                <span className="material-symbols-outlined shrink-0 text-red-500">error</span>
                Error loading history: {error}
            </div>
        );
    }

    if (runs.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-16 mt-4 text-center glass-panel rounded-2xl border-dashed border-2 border-slate-300 dark:border-slate-700">
                <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4 text-3xl">📭</div>
                <h3 className="text-xl font-bold text-text-dark dark:text-white mb-2">No History Found</h3>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400 max-w-sm">
                    Start a pipeline run and complete the HITL review to save results to the database.
                </p>
            </div>
        );
    }

    return (
        <div className="glass-panel border-slate-200 dark:border-slate-800 rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-none overflow-hidden mt-2 relative">
            <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 flex justify-between items-center backdrop-blur-sm sticky top-0 z-10">
                <h2 className="text-[14px] font-black text-slate-700 dark:text-slate-200 uppercase tracking-widest flex items-center gap-2">
                    <span className="material-symbols-outlined text-[18px] text-accent-blue">history</span>
                    Execution Archive
                </h2>
                <div className="px-3 py-1 bg-white/50 dark:bg-slate-800/50 rounded-full border border-slate-200 dark:border-slate-700 shadow-sm text-xs font-bold text-slate-500 dark:text-slate-400">
                    Total Records: <span className="text-text-dark dark:text-white">{runs.length}</span>
                </div>
            </div>

            <div className="overflow-x-auto bg-white/20 dark:bg-[#0A0D15]/40 backdrop-blur-sm">
                <table className="w-full text-sm text-left align-middle border-collapse">
                    <thead className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest border-b border-slate-200 dark:border-slate-800">
                        <tr>
                            <th className="px-6 py-4">Operation Target</th>
                            <th className="px-6 py-4">Queue / Window</th>
                            <th className="px-6 py-4">Verification State</th>
                            <th className="px-6 py-4 cursor-pointer hover:text-accent-blue transition-colors flex items-center gap-1 group">
                                Timestamp
                                <span className="material-symbols-outlined text-[14px] opacity-0 group-hover:opacity-100 transition-opacity">arrow_downward</span>
                            </th>
                            <th className="px-6 py-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                        {runs.map((run) => {
                            const date = new Date(run.created_at);
                            return (
                                <tr key={run.run_id} className="hover:bg-white/40 dark:hover:bg-slate-800/30 transition-colors group">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 flex items-center justify-center text-[16px]">
                                                {run.flow_type === "schedule" ? "📅" : run.flow_type === "training" ? "🎯" : run.flow_type === "hybrid" ? "🔄" : run.flow_type === "shift_swap" ? "🔀" : "📊"}
                                            </div>
                                            <span className="font-bold text-text-dark dark:text-slate-200 capitalize tracking-tight">
                                                {run.flow_type.replace("_", " ")}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="text-text-dark dark:text-slate-200 font-bold text-xs">{run.queue_id}</div>
                                        <div className="text-slate-500 dark:text-slate-400 text-[11px] font-medium mt-0.5">{run.time_window}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        {getStatusToken(run.status)}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="text-text-dark dark:text-slate-300 font-medium text-xs tabular-nums">{date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}</div>
                                        <div className="text-slate-400 dark:text-slate-500 text-[10px] uppercase font-bold tracking-wider mt-0.5 tabular-nums">{date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <button
                                            onClick={() => onSelectRun(run.run_id)}
                                            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold uppercase tracking-wider text-accent-blue dark:text-blue-400 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-accent-blue/30 transition-all shadow-sm active:scale-[0.97]"
                                        >
                                            <span className="material-symbols-outlined text-[16px]">visibility</span>
                                            Inspect
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
