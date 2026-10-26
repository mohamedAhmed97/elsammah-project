import { useState, useCallback, useRef } from "react";
import RunForm from "./components/RunForm";
import LiveConsole from "./components/LiveConsole";
import HITLModal from "./components/HITLModal";
import ResultsPanel from "./components/ResultsPanel";
import HistoryPanel from "./components/HistoryPanel";
import PipelineVisualizer from "./components/PipelineVisualizer";
import type {
  AuditLogEntry,
  BPOFlowState,
  FlowStartRequest,
  FlowType,
  HITLDecisionRequest,
} from "./types";

const API_BASE = "/api";

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [flowState, setFlowState] = useState<BPOFlowState | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [currentStep, setCurrentStep] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [viewMode, setViewMode] = useState<"run" | "history">("run");
  const [showHITL, setShowHITL] = useState(false);
  const [activeFlowType, setActiveFlowType] = useState<FlowType | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs for cleanup
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  // ── Cleanup helper ──
  const stopPollingAndSSE = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }
  }, []);

  // ── Add Log Entry ──
  const addLogEntry = useCallback(
    (eventType: string, stepName: string, message: string) => {
      setAuditLog((prev) => [
        ...prev,
        {
          timestamp: new Date().toISOString(),
          step_name: stepName,
          event_type: eventType,
          message,
        },
      ]);
    },
    []
  );

  // ── Start a new flow ──
  const handleStartFlow = useCallback(
    async (request: FlowStartRequest) => {
      stopPollingAndSSE();

      setError(null);
      setAuditLog([]);
      setCurrentStep("");
      setShowHITL(false);
      setFlowState(null);
      setIsRunning(true);
      setActiveFlowType(request.flow_type);
      setViewMode("run");

      try {
        const res = await fetch(`${API_BASE}/flow/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        });

        if (!res.ok) {
          const errData = await res.json();
          setError(errData.detail?.message || "Failed to start flow");
          setIsRunning(false);
          return;
        }

        const data = await res.json();
        setRunId(data.run_id);

        subscribeToSSE(data.run_id);
        pollRef.current = setInterval(() => fetchState(data.run_id), 5000);
      } catch (err) {
        setError(`Connection error: ${err}`);
        setIsRunning(false);
      }
    },
    [stopPollingAndSSE]
  );

  // ── Load a past run from history ──
  const handleSelectHistoryRun = useCallback(async (selectedRunId: string) => {
    try {
      const baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const res = await fetch(`${baseUrl}/api/flow/history/${selectedRunId}`);
      if (!res.ok) throw new Error("Failed to load historical run details");

      const pastState = await res.json();
      setRunId(selectedRunId);
      setFlowState(pastState);
      setAuditLog(pastState.audit_log || []);
      setCurrentStep(pastState.current_step || "finalize");
      setIsRunning(false);
      setViewMode("run");
    } catch (err) {
      setError(`Failed to load history: ${err}`);
    }
  }, []);

  // ── Fetch state once ──
  const fetchState = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/flow/${id}/state`);
      if (res.ok) {
        const state = await res.json();
        setFlowState(state);
        setCurrentStep(state.current_step || "");
      }
    } catch {
      // Silently fail on poll errors
    }
  };

  // ── SSE Subscription ──
  const subscribeToSSE = (id: string) => {
    const source = new EventSource(`${API_BASE}/flow/${id}/stream`);
    sseRef.current = source;

    source.addEventListener("step_started", (e) => {
      const data = JSON.parse(e.data);
      setCurrentStep(data.step || "");
      addLogEntry("step_started", data.step, `Step started: ${data.step}`);
    });

    source.addEventListener("step_completed", (e) => {
      const data = JSON.parse(e.data);
      addLogEntry("step_completed", data.step, `Step completed: ${data.step}`);
    });

    source.addEventListener("leave_overlap_detected", (e) => {
      const data = JSON.parse(e.data);
      addLogEntry(
        "hitl_required",
        "analyze_leave",
        `Leave overlaps detected (severity: ${data.severity})`
      );
    });

    source.addEventListener("swap_feasibility", (e) => {
      const data = JSON.parse(e.data);
      addLogEntry(
        "step_completed",
        "coordinate_swap",
        `Swap feasibility: ${data.feasible ? "Feasible" : "Not feasible"}`
      );
    });

    source.addEventListener("hitl_required", () => {
      addLogEntry(
        "hitl_required",
        "hitl_checkpoint",
        "HITL -- Awaiting manager decision"
      );
      setShowHITL(true);
      fetchState(id);
    });

    source.addEventListener("hitl_resolved", (e) => {
      const data = JSON.parse(e.data);
      addLogEntry(
        "hitl_resolved",
        "hitl_checkpoint",
        `HITL resolved: ${data.decision}`
      );
      setShowHITL(false);
    });

    source.addEventListener("flow_completed", () => {
      addLogEntry("flow_completed", "finalize", "Flow completed");
      setIsRunning(false);
      fetchState(id);
      stopPollingAndSSE();
    });

    source.addEventListener("flow_error", (e) => {
      const data = JSON.parse(e.data);
      addLogEntry(
        "error",
        data.step || "unknown",
        `Error: ${data.message}`
      );
      setIsRunning(false);
      stopPollingAndSSE();
    });

    source.onerror = () => {
      stopPollingAndSSE();
      setIsRunning(false);
    };
  };

  // ── Submit HITL Decision ──
  const handleHITLDecision = async (decision: HITLDecisionRequest) => {
    if (!runId) return;

    try {
      const res = await fetch(`${API_BASE}/flow/${runId}/hitl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(decision),
      });

      if (!res.ok) {
        const errData = await res.json();
        setError(errData.detail?.message || "Failed to submit decision");
      }

      setShowHITL(false);
    } catch (err) {
      setError(`Connection error: ${err}`);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background-light dark:bg-background-dark font-display text-text-dark dark:text-text-light transition-colors duration-300">

      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col justify-between border-r border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md h-full z-20 transition-colors duration-300">
        <div className="flex flex-col gap-6 p-6 h-full overflow-y-auto">
          {/* Logo Area */}
          <div className="flex items-center gap-3">
            <div className="bg-center bg-no-repeat bg-cover rounded-xl w-10 h-10 shadow-sm border border-slate-100 dark:border-slate-700 bg-primary/20 flex items-center justify-center">
              <span className="material-symbols-outlined text-accent-blue font-bold">dataset</span>
            </div>
            <div className="flex flex-col">
              <h1 className="text-text-dark dark:text-white text-lg font-bold leading-tight">Elsam3a</h1>
              <p className="text-slate-500 dark:text-slate-400 text-xs font-medium">Ops Cockpit v2.0</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex flex-col gap-2">
            <button
              onClick={() => {
                if (!isRunning) {
                  setRunId(null);
                  setFlowState(null);
                  setAuditLog([]);
                  setCurrentStep("");
                }
                setViewMode("run");
              }}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium ${viewMode === "run" ? "bg-accent-blue/10 text-accent-blue dark:text-blue-300 font-semibold" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-text-dark dark:hover:text-white"}`}
            >
              <span className="material-symbols-outlined text-[20px]">dashboard</span>
              <span className="text-sm">Dashboard</span>
            </button>
            <button
              onClick={() => setViewMode("history")}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium ${viewMode === "history" ? "bg-accent-blue/10 text-accent-blue dark:text-blue-300 font-semibold" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-text-dark dark:hover:text-white"}`}
            >
              <span className="material-symbols-outlined text-[20px]">analytics</span>
              <span className="text-sm">History</span>
            </button>
          </nav>

          {/* Start Form CTA Area */}
          <div className="mt-auto">
            <RunForm onSubmit={handleStartFlow} disabled={isRunning} />
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
          <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] bg-blue-200/40 dark:bg-blue-900/20 rounded-full blur-3xl mix-blend-multiply dark:mix-blend-screen animate-pulse"></div>
          <div className="absolute top-[20%] right-[10%] w-[400px] h-[400px] bg-purple-200/40 dark:bg-purple-900/20 rounded-full blur-3xl mix-blend-multiply dark:mix-blend-screen animate-pulse delay-700"></div>
          <div className="absolute bottom-[-10%] left-[40%] w-[600px] h-[600px] bg-indigo-200/40 dark:bg-indigo-900/20 rounded-full blur-3xl mix-blend-multiply dark:mix-blend-screen animate-pulse delay-1000"></div>
        </div>

        {/* Top Header Area */}
        <header className="flex-shrink-0 px-8 py-6 flex flex-wrap justify-between items-end gap-4 z-10">
          <div className="flex flex-col gap-1">
            <h2 className="text-4xl font-black tracking-tight text-text-dark dark:text-white">The Ops Cockpit</h2>
            <p className="text-slate-500 dark:text-slate-400 text-base font-medium flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${isRunning ? "bg-amber-500 animate-pulse" : "bg-green-500"}`}></span>
              Real-time BPO Agentic Pipeline Monitor
            </p>
          </div>
          <div className="flex gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass-panel border border-slate-200 dark:border-slate-700 shadow-sm">
              <div className={`w-2 h-2 ${error ? "bg-red-500" : "bg-green-500"} rounded-full`}></div>
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{error ? "Error" : "System Healthy"}</span>
            </div>
          </div>
        </header>

        {/* Dynamic Content Area */}
        <div className="flex-1 overflow-y-auto px-8 pb-8 scrollbar-hide">
          {error && (
            <div className="mb-6 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex justify-between items-center shadow-sm">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 font-bold px-2 py-1">&times;</button>
            </div>
          )}

          {viewMode === "history" ? (
            <HistoryPanel onSelectRun={handleSelectHistoryRun} />
          ) : (
            <div className="flex flex-col gap-6 h-full min-h-[600px]">

              {/* Dynamic Tree Graph Visualizer */}
              {runId && (
                <PipelineVisualizer entries={auditLog} currentStep={currentStep} flowType={flowState?.flow_type || activeFlowType || "hybrid"} />
              )}

              <div className="flex flex-col lg:flex-row gap-6 flex-1 h-full min-h-[500px]">
                {/* Left Column (Results Output) */}
                <div className="flex-1 flex flex-col gap-6">
                  <ResultsPanel flowState={flowState} isRunning={isRunning} currentStep={currentStep} />
                </div>

                {/* Right Column (Live Console) */}
                <div className="w-full lg:w-96 flex-shrink-0 flex flex-col h-[600px]">
                  <LiveConsole entries={auditLog} currentStep={currentStep} />
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* HITL Modal Overlay */}
      {showHITL && flowState && (
        <HITLModal
          flowState={flowState}
          onDecision={handleHITLDecision}
          onClose={() => setShowHITL(false)}
        />
      )}
    </div>
  );
}

