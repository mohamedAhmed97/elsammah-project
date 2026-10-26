import React from "react";
import type { AuditLogEntry, FlowType } from "../types";

export interface PipelineVisualizerProps {
    entries: AuditLogEntry[];
    currentStep: string;
    flowType?: FlowType;
}

type NodeState = "pending" | "active" | "completed" | "skipped" | "error" | "hitl";

interface PipelineNode {
    id: string;
    label: string;
    icon: string;
}

const NODES_DATA: Record<string, PipelineNode> = {
    input_gatekeeper: { id: "input_gatekeeper", label: "Gatekeeper", icon: "door_front" },
    analyze_transcripts: { id: "analyze_transcripts", label: "Transcripts", icon: "description" },
    forecast_demand: { id: "forecast_demand", label: "Forecast", icon: "trending_up" },
    analyze_leave: { id: "analyze_leave", label: "Leave", icon: "event_busy" },
    generate_schedule: { id: "generate_schedule", label: "Schedule", icon: "calendar_month" },
    design_training: { id: "design_training", label: "Training", icon: "school" },
    coordinate_swap: { id: "coordinate_swap", label: "Swap", icon: "sync_alt" },
    leave_review_dummy: { id: "leave_review_dummy", label: "Review", icon: "visibility" },
    hitl_checkpoint: { id: "hitl_checkpoint", label: "HITL", icon: "front_hand" },
    finalize: { id: "finalize", label: "Finalize", icon: "task_alt" }
};

type LayoutColumn = string | string[];

const FLOW_LAYOUTS: Record<string, LayoutColumn[]> = {
    schedule: [
        "input_gatekeeper",
        "analyze_transcripts",
        ["forecast_demand", "analyze_leave"],
        "generate_schedule",
        "hitl_checkpoint",
        "finalize"
    ],
    hybrid: [
        "input_gatekeeper",
        "analyze_transcripts",
        ["forecast_demand", "analyze_leave"],
        ["generate_schedule", "design_training"],
        "hitl_checkpoint",
        "finalize"
    ],
    training: ["input_gatekeeper", "analyze_transcripts", "design_training", "hitl_checkpoint", "finalize"],
    shift_swap: ["input_gatekeeper", "analyze_leave", "coordinate_swap", "hitl_checkpoint", "finalize"],
    leave_review: ["input_gatekeeper", "analyze_leave", "leave_review_dummy", "hitl_checkpoint", "finalize"]
};

export default function PipelineVisualizer({ entries, currentStep, flowType = "hybrid" }: PipelineVisualizerProps) {
    // Helper to determine node state
    const getNodeState = (nodeId: string): NodeState => {
        // Handle leave_review_dummy state so it acts like an operation node
        if (nodeId === "leave_review_dummy") {
            const hasHitlReq = entries.some(e => e.event_type === "hitl_required" || e.event_type === "hitl_resolved");
            if (hasHitlReq) return "completed";
            if (entries.some(e => e.step_name === "analyze_leave" && e.event_type === "step_completed")) return "active";
            return "pending";
        }

        let hasError = false;
        let isCompleted = false;
        let isSkipped = false;
        let isStarted = false;
        let isHitlRequired = false;

        for (const entry of entries) {
            if (entry.step_name === nodeId) {
                if (entry.event_type === "step_started") isStarted = true;
                if (entry.event_type === "step_completed") isCompleted = true;
                if (entry.event_type === "step_skipped") isSkipped = true;
                if (entry.event_type === "error" || entry.event_type === "flow_error") hasError = true;
            }
            if (nodeId === "hitl_checkpoint") {
                if (entry.step_name === "hitl_checkpoint" && entry.event_type === "hitl_required") isHitlRequired = true;
                if (entry.step_name === "hitl_checkpoint" && entry.event_type === "hitl_resolved") isCompleted = true;
            }
        }

        if (hasError) return "error";

        // Finalize state handling
        if (nodeId === "finalize") {
            const hasFinalized = entries.some(e => e.step_name === "finalize" && e.event_type === "flow_completed");
            if (hasFinalized) return "completed";
            if (currentStep === "finalize") return "active";
        }

        if (isSkipped) return "skipped";
        if (nodeId === "hitl_checkpoint" && isHitlRequired && !isCompleted) return "hitl";
        if (isCompleted) return "completed";
        if (isStarted) return "active";

        if (nodeId === currentStep) return "active";

        return "pending";
    };

    // Component to render individual nodes
    const Node = ({ node, isBranch = false, isActiveBranch = false, style, dimLabel = false, parallelBadge = false }: { node: PipelineNode, isBranch?: boolean, isActiveBranch?: boolean, style?: React.CSSProperties, dimLabel?: boolean, parallelBadge?: boolean }) => {
        const state = getNodeState(node.id);

        let ringClass = "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm";
        let iconClass = "text-slate-400";
        let glowClass = "";
        let labelClass = "text-slate-500 opacity-60";

        // If it's a branch node that is NOT the active flow type, dim it
        const isDimmed = isBranch && !isActiveBranch;

        if (state === "completed") {
            ringClass = "border-green-500 bg-white dark:bg-slate-900 border-[3px]";
            iconClass = "text-green-500 font-bold";
            labelClass = "text-green-600 dark:text-green-400 font-bold opacity-100";
        } else if (state === "active") {
            ringClass = "border-accent-blue bg-white dark:bg-slate-900 shadow-[0_0_15px_rgba(41,0,200,0.4)] border-[3px]";
            iconClass = "text-accent-blue font-bold";
            glowClass = "animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-blue opacity-30";
            labelClass = "text-accent-blue font-black opacity-100";
        } else if (state === "hitl") {
            ringClass = "border-amber-500 bg-amber-50 dark:bg-amber-900/30 shadow-[0_0_15px_rgba(245,158,11,0.5)] border-[3px]";
            iconClass = "text-amber-500 font-bold animate-pulse";
            glowClass = "animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-500 opacity-20";
            labelClass = "text-amber-600 dark:text-amber-400 font-black opacity-100 animate-pulse";
        } else if (state === "error") {
            ringClass = "border-red-500 bg-red-50 dark:bg-red-900/30 shadow-[0_0_15px_rgba(239,68,68,0.5)] border-[3px]";
            iconClass = "text-red-500";
            labelClass = "text-red-600 dark:text-red-400 font-black opacity-100";
        } else if (state === "skipped" || isDimmed) {
            ringClass = "border-slate-200 dark:border-slate-800 bg-transparent opacity-30";
            iconClass = "text-slate-400";
            labelClass = "text-slate-400 opacity-30";
        }

        if (dimLabel && state !== "active" && state !== "completed" && state !== "error" && state !== "hitl") {
            labelClass = "text-slate-400 opacity-40";
        }

        return (
            <div className="absolute flex flex-col items-center justify-center z-10 w-24 -ml-12" style={style}>
                <div className={`relative flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-full transition-all duration-300 ${ringClass}`}>
                    {glowClass && <span className={glowClass}></span>}
                    {state === "completed" ? (
                        <span className={`material-symbols-outlined text-[20px] sm:text-[24px] ${iconClass}`}>check</span>
                    ) : state === "error" ? (
                        <span className={`material-symbols-outlined text-[20px] sm:text-[24px] ${iconClass}`}>close</span>
                    ) : (
                        <span className={`material-symbols-outlined text-[20px] sm:text-[24px] ${state === 'active' ? 'animate-pulse' : ''} ${iconClass}`}>{node.icon}</span>
                    )}
                </div>
                <span className={`absolute -bottom-7 text-[10px] sm:text-[11px] font-bold uppercase tracking-widest whitespace-nowrap transition-all duration-300 ${labelClass}`}>
                    {node.label}
                </span>
                {/* Parallel execution badge */}
                {parallelBadge && (
                    <span className="absolute -top-3 -right-1 bg-indigo-500 text-white text-[8px] font-black px-1.5 py-0.5 rounded-full leading-none tracking-wider shadow-lg">
                        ∥
                    </span>
                )}
            </div>
        );
    };

    const getLineColor = (fromNode: string, toNode: string | null = null, forceDim: boolean = false) => {
        if (forceDim) return "stroke-slate-200 dark:stroke-slate-800 opacity-30";
        const fromState = getNodeState(fromNode);

        // If the source node wasn't executed, don't color its outgoing line green
        if (fromState !== "completed" && fromState !== "active") {
            return "stroke-slate-200 dark:stroke-slate-800 opacity-30";
        }

        if (toNode) {
            const toState = getNodeState(toNode);
            // The line is active/completed if the destination node is part of the flow
            if (['active', 'completed', 'hitl', 'error'].includes(toState)) {
                return "stroke-green-500";
            }
        }
        return "stroke-slate-200 dark:stroke-slate-800 opacity-30";
    };

    const activeLayout = FLOW_LAYOUTS[flowType] || FLOW_LAYOUTS.hybrid;
    const stepPercent = 100 / (activeLayout.length + 1);

    const getTopPercent = (rowIndex: number, totalNodes: number) => {
        if (totalNodes === 1) return 50;
        if (totalNodes === 2) return rowIndex === 0 ? 30 : 70;
        if (totalNodes === 3) return rowIndex === 0 ? 20 : rowIndex === 1 ? 50 : 80;
        return 50;
    };

    return (
        <div className="w-full h-80 my-6 glass-panel rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative z-10 shrink-0 overflow-hidden">
            <div className="w-full h-full relative max-w-5xl mx-auto">

                {/* SVG Connections */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
                    {activeLayout.map((columnData, colIndex) => {
                        if (colIndex === activeLayout.length - 1) return null;

                        const nextColumnData = activeLayout[colIndex + 1];
                        const currNodes = Array.isArray(columnData) ? columnData : [columnData];
                        const nextNodes = Array.isArray(nextColumnData) ? nextColumnData : [nextColumnData];

                        const x1 = `${(colIndex + 1) * stepPercent}%`;
                        const x2 = `${(colIndex + 2) * stepPercent}%`;

                        return currNodes.flatMap((fromNodeId, fromIndex) => {
                            const y1 = `${getTopPercent(fromIndex, currNodes.length)}%`;

                            return nextNodes.map((toNodeId, toIndex) => {
                                const y2 = `${getTopPercent(toIndex, nextNodes.length)}%`;
                                return (
                                    <line
                                        key={`line-${fromNodeId}-${toNodeId}`}
                                        x1={x1}
                                        y1={y1}
                                        x2={x2}
                                        y2={y2}
                                        className={`transition-all duration-500 ${getLineColor(fromNodeId, toNodeId)} stroke-[3px]`}
                                        strokeLinecap="round"
                                    />
                                );
                            });
                        });
                    })}
                </svg>

                {/* Nodes */}
                {activeLayout.map((columnData, colIndex) => {
                    const colNodes = Array.isArray(columnData) ? columnData : [columnData];
                    const left = `${(colIndex + 1) * stepPercent}%`;

                    return colNodes.map((nodeId, rowIndex) => {
                        const node = NODES_DATA[nodeId];
                        if (!node) return null;

                        const topPercent = getTopPercent(rowIndex, colNodes.length);

                        return (
                            <Node
                                key={nodeId}
                                node={node}
                                style={{ left, top: `calc(${topPercent}% - 24px)` }}
                            />
                        );
                    });
                })}
            </div>
        </div>
    );
}

