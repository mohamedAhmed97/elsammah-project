import { useState } from "react";
import type { BPOFlowState, HITLDecisionRequest } from "../types";
import ResultsPanel from "./ResultsPanel";

interface HITLModalProps {
    flowState: BPOFlowState;
    onDecision: (decision: HITLDecisionRequest) => void;
    onClose: () => void;
}

export default function HITLModal({ flowState, onDecision, onClose }: HITLModalProps) {
    const [decision, setDecision] = useState<"approve" | "reject" | "edit">("approve");
    const [comments, setComments] = useState("");
    const [reviewerId, setReviewerId] = useState("manager-001");
    const [showOverlapsModal, setShowOverlapsModal] = useState(false);

    const handleSubmit = () => {
        onDecision({
            decision,
            reviewer_id: reviewerId,
            comments,
        });
    };

    const pendingOutputs: string[] = [];
    if (flowState.schedule_output) pendingOutputs.push("Schedule");
    if (flowState.training_plan) pendingOutputs.push("Training Plan");
    if (flowState.swap_result) pendingOutputs.push("Shift Swap");
    if (flowState.leave_report) pendingOutputs.push("Leave Report");

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/60 backdrop-blur-md">
            <div className="glass-panel w-full max-w-6xl flex flex-col md:flex-row max-h-[90vh] overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800 shadow-[0_8px_32px_rgb(0,0,0,0.12)]">

                {/* Left Side: Decision Form */}
                <div className="w-full md:w-[45%] flex flex-col border-r border-slate-200 dark:border-slate-800 overflow-y-auto bg-white/50 dark:bg-[#070B14]/80">
                    {/* Header */}
                    <div className="px-6 py-5 bg-gradient-to-r from-amber-500/10 to-transparent border-b border-slate-200 dark:border-slate-800 shrink-0 flex items-start gap-4">
                        <div className="w-10 h-10 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-500 flex items-center justify-center shrink-0">
                            <span className="material-symbols-outlined">front_hand</span>
                        </div>
                        <div>
                            <h3 className="text-lg font-black text-slate-800 dark:text-white uppercase tracking-wide">
                                Human Review Required
                            </h3>
                            <p className="text-xs font-bold text-slate-500 dark:text-slate-400 mt-1 uppercase tracking-wider">
                                EU AI Act Compliance
                            </p>
                        </div>
                    </div>

                    {/* Pending Outputs Summary */}
                    <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800 shrink-0">
                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-3">Pending Items for Review</p>
                        <div className="flex flex-wrap gap-2">
                            {pendingOutputs.map((output) => (
                                <span
                                    key={output}
                                    className="px-2.5 py-1 rounded-md bg-accent-blue/10 border border-accent-blue/20 text-accent-blue dark:text-blue-400 text-[10px] font-bold uppercase tracking-wider shadow-sm"
                                >
                                    {output}
                                </span>
                            ))}
                        </div>

                        {/* Swap result details */}
                        {flowState.swap_result && (
                            <div className={`mt-4 p-3 rounded-lg border ${flowState.swap_result.feasible ? "bg-green-500/5 border-green-500/20 text-green-700 dark:text-green-400" : "bg-red-500/5 border-red-500/20 text-red-700 dark:text-red-400"} text-xs font-bold uppercase tracking-wider flex items-center gap-2`}>
                                <span className="material-symbols-outlined text-[16px]">{flowState.swap_result.feasible ? "check_circle" : "cancel"}</span>
                                Swap Feasibility: {flowState.swap_result.feasible ? "Feasible" : "Not Feasible"}
                            </div>
                        )}

                        {/* Leave overlap summary */}
                        {flowState.leave_report && flowState.leave_report.overlaps.length > 0 && (
                            <button
                                type="button"
                                onClick={() => setShowOverlapsModal(true)}
                                className="mt-4 w-full p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 text-amber-700 dark:text-amber-500 text-xs font-bold uppercase tracking-wider flex items-center justify-between gap-2 hover:bg-amber-500/10 transition-colors cursor-pointer text-left"
                            >
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[16px]">warning</span>
                                    {flowState.leave_report.overlaps.length} leave overlap(s) detected
                                </div>
                                <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                            </button>
                        )}
                    </div>

                    {/* Decision Form */}
                    <div className="px-6 py-5 space-y-5 flex-1 glass-panel-inner">
                        <div>
                            <label htmlFor="reviewer-id" className="block text-[10px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 mb-2">Reviewer ID</label>
                            <input
                                id="reviewer-id"
                                type="text"
                                value={reviewerId}
                                onChange={(e) => setReviewerId(e.target.value)}
                                className="w-full px-4 py-2.5 rounded-lg bg-white/50 dark:bg-[#0A0D15]/50 border border-slate-200 dark:border-slate-700 text-text-dark dark:text-white text-sm outline-none focus:border-accent-blue focus:ring-1 focus:ring-accent-blue/50 transition-all font-mono shadow-inner"
                            />
                        </div>

                        <div>
                            <label className="block text-[10px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 mb-2">Final Decision</label>
                            <div className="grid grid-cols-2 gap-2">
                                {/* TODO: Re-enable edit button when implemented
                                {(["approve", "edit", "reject"] as const).map((d) => ( */}
                                {(["approve", "reject"] as const).map((d) => (
                                    <button
                                        key={d}
                                        type="button"
                                        onClick={() => setDecision(d)}
                                        className={`px-3 py-2.5 rounded-lg text-[11px] font-black uppercase tracking-wider transition-all flex flex-col items-center gap-1 border ${decision === d
                                            ? d === "approve"
                                                ? "bg-green-500/10 border-green-500 text-green-700 dark:text-green-400 shadow-[0_0_15px_rgba(34,197,94,0.15)]"
                                                : "bg-red-500/10 border-red-500 text-red-700 dark:text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.15)]"
                                            : "bg-white/40 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-white/80 dark:hover:bg-slate-700/60 hover:border-slate-300 dark:hover:border-slate-600 shadow-sm"
                                            }`}
                                    >
                                        <span className="material-symbols-outlined text-[20px] mb-0.5">{d === "approve" ? "check_circle" : "cancel"}</span>
                                        {d}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div>
                            <label htmlFor="comments" className="flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 mb-2">
                                <span>Comments</span>
                                <span className="text-amber-600 dark:text-amber-500 normal-case tracking-normal font-bold bg-amber-500/10 px-1.5 py-0.5 rounded">Required for Audit</span>
                            </label>
                            <textarea
                                id="comments"
                                value={comments}
                                onChange={(e) => setComments(e.target.value)}
                                rows={3}
                                className="w-full px-4 py-3 rounded-lg bg-white/50 dark:bg-[#0A0D15]/50 border border-slate-200 dark:border-slate-700 text-text-dark dark:text-white text-sm resize-none outline-none focus:border-accent-blue focus:ring-1 focus:ring-accent-blue/50 transition-all shadow-inner placeholder:text-slate-400 dark:placeholder:text-slate-600"
                                placeholder="Provide justification for your decision..."
                            />
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="px-6 py-5 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-3 shrink-0 bg-white/30 dark:bg-slate-900/30">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-5 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all shadow-sm"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={handleSubmit}
                            disabled={!comments.trim() || !reviewerId.trim()}
                            className="px-6 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider bg-accent-blue text-white hover:bg-blue-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_4px_12px_rgba(40,0,200,0.3)] disabled:shadow-none flex items-center gap-2 group"
                        >
                            Submit Decision
                            <span className="material-symbols-outlined text-[16px] group-hover:translate-x-0.5 transition-transform">send</span>
                        </button>
                    </div>
                </div>

                {/* Right Side: Results Preview */}
                <div className="w-full md:w-[55%] flex flex-col bg-white/20 dark:bg-[#0A0D15]/60 border-t md:border-t-0 border-slate-200 dark:border-slate-800 relative">
                    <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 shrink-0 flex items-center gap-2">
                        <span className="material-symbols-outlined text-slate-400 text-[18px]">visibility</span>
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-600 dark:text-slate-300">
                            Generated Results Preview
                        </h3>
                    </div>
                    <div className="flex-1 p-6 overflow-hidden bg-slate-50/50 dark:bg-slate-900/20">
                        {/* Wrapper for scrolling the results inside modal smoothly without scrollbar */}
                        <div className="h-full w-full overflow-y-auto pr-2" style={{ scrollbarWidth: 'thin' }}>
                            <ResultsPanel flowState={flowState} isRunning={false} />
                        </div>
                    </div>
                </div>

            </div>

            {/* Overlaps Modal */}
            {showOverlapsModal && flowState.leave_report && (
                <div className="absolute inset-0 z-[60] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-sm rounded-2xl">
                    <div className="bg-white dark:bg-[#0A0D15] border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden">
                        <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-amber-500/5">
                            <h3 className="text-sm font-black uppercase tracking-widest text-slate-800 dark:text-white flex items-center gap-2">
                                <span className="material-symbols-outlined text-amber-500">warning</span>
                                Detected Leave Overlaps
                            </h3>
                            <button
                                onClick={() => setShowOverlapsModal(false)}
                                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                            >
                                <span className="material-symbols-outlined text-[20px]">close</span>
                            </button>
                        </div>
                        <div className="p-5 overflow-y-auto space-y-3" style={{ scrollbarWidth: 'thin' }}>
                            {flowState.leave_report.overlaps.map((overlap, idx) => (
                                <div key={idx} className="p-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex flex-col gap-2">
                                    <div className="flex justify-between items-start">
                                        <div className="font-bold text-sm text-slate-800 dark:text-white flex items-center gap-2">
                                            <span className="material-symbols-outlined text-[18px] text-slate-400">group</span>
                                            {overlap.agent_a_id} <span className="text-slate-400 font-normal mx-1">and</span> {overlap.agent_b_id}
                                        </div>
                                        <span
                                            className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${overlap.severity === 'critical' ? 'bg-red-500/10 text-red-600 dark:text-red-400' :
                                                overlap.severity === 'medium' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                                                    'bg-green-500/10 text-green-600 dark:text-green-400'
                                                }`}
                                            title={
                                                overlap.severity === 'critical' ? 'Severe overlap: Immediate action required to prevent coverage failure.' :
                                                    overlap.severity === 'medium' ? 'Moderate overlap: Please review to ensure sufficient queue coverage.' :
                                                        'Low severity: Minor overlap with adequate coverage remaining.'
                                            }
                                        >
                                            {overlap.severity}
                                        </span>
                                    </div>
                                    <div className="text-xs text-slate-600 dark:text-slate-400 flex items-center gap-1.5 mt-1">
                                        <span className="material-symbols-outlined text-[14px]">event</span>
                                        {overlap.overlap_start} <span className="mx-1">→</span> {overlap.overlap_end}
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="px-5 py-4 border-t border-slate-200 dark:border-slate-800 flex justify-end bg-slate-50/50 dark:bg-slate-800/30">
                            <button
                                onClick={() => setShowOverlapsModal(false)}
                                className="px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
