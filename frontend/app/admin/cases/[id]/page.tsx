"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getCaseFull, submitCaseDecision, runScreening, updateCase } from "@/lib/api";
import type { FullCase } from "@/lib/types";
import {
  ArrowLeft, User, FileText, Shield, AlertTriangle, Bot,
  CheckCircle, XCircle, RefreshCw, ClipboardList, Activity,
  ChevronDown, ChevronUp, Zap, Flag,
} from "lucide-react";

const PRIORITY_STYLES: Record<string, string> = {
  critical: "text-red-700 bg-red-100 border-red-300",
  high: "text-orange-700 bg-orange-50 border-orange-300",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low: "text-emerald-700 bg-emerald-50 border-emerald-200",
};

const DECISION_CONFIG = {
  APPROVE: { label: "Approve", bg: "bg-emerald-600 hover:bg-emerald-700", icon: CheckCircle },
  REJECT: { label: "Reject", bg: "bg-red-600 hover:bg-red-700", icon: XCircle },
  EDD_REQUIRED: { label: "EDD Required", bg: "bg-amber-500 hover:bg-amber-600", icon: ClipboardList },
  MANUAL_REVIEW: { label: "Manual Review", bg: "bg-blue-600 hover:bg-blue-700", icon: Shield },
} as const;

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<FullCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Decision modal
  const [decisionMode, setDecisionMode] = useState<keyof typeof DECISION_CONFIG | null>(null);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [sarFiled, setSarFiled] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [decisionError, setDecisionError] = useState("");
  const [decisionSuccess, setDecisionSuccess] = useState("");

  // Rescreening
  const [rescreening, setRescreening] = useState(false);
  const [rescreenResult, setRescreenResult] = useState<{ message: string; score?: number | null; tier?: string | null; decision?: string | null } | null>(null);

  // Expandable sections
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    customer: true,
    kyc: true,
    alerts: true,
    risk: true,
    documents: false,
    agents: false,
    notes: true,
  });

  const toggle = (key: string) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const fetchData = async () => {
    if (!token || !id) return;
    try {
      const result = await getCaseFull(id, token);
      setData(result);
    } catch {
      setError("Case not found or access denied.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [token, id]);

  const handleDecision = async () => {
    if (!token || !id || !decisionMode) return;
    if (!decisionNotes.trim()) {
      setDecisionError("Decision notes are required.");
      return;
    }
    setSubmitting(true);
    setDecisionError("");
    try {
      await submitCaseDecision(id, {
        decision: decisionMode,
        notes: decisionNotes,
        reason: decisionReason || undefined,
        sar_filed: sarFiled,
      }, token);
      setDecisionSuccess(`Decision recorded: ${decisionMode}`);
      setDecisionMode(null);
      setDecisionNotes("");
      setDecisionReason("");
      setSarFiled(false);
      fetchData();
    } catch (err: unknown) {
      setDecisionError(err instanceof Error ? err.message : "Failed to submit decision.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRescreen = async () => {
    if (!token || !data) return;
    setRescreening(true);
    setRescreenResult(null);
    try {
      const result = await runScreening(data.case.customer_id, token);
      setRescreenResult(result);
      fetchData();
    } catch (err: unknown) {
      setRescreenResult({ message: err instanceof Error ? err.message : "Rescreening failed." });
    } finally {
      setRescreening(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
        <p className="text-red-700 font-semibold">{error || "Case not found."}</p>
        <button onClick={() => router.back()} className="mt-4 text-sm text-red-600 underline">Go back</button>
      </div>
    );
  }

  const { case: c, customer, kyc_profile, documents, risk_scores, alerts, agent_logs } = data;
  const latestRisk = risk_scores[0];

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Cases
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-zinc-900">Case Investigation</h1>
          <p className="text-xs text-zinc-500 font-mono">{c.id}</p>
        </div>
        <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold uppercase ${PRIORITY_STYLES[c.priority] ?? ""}`}>
          {c.priority}
        </span>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold capitalize ${c.status === "approved" ? "text-emerald-700 bg-emerald-50" : c.status === "rejected" ? "text-red-700 bg-red-50" : "text-amber-700 bg-amber-50"}`}>
          {c.status.replace("_", " ")}
        </span>
        {c.sar_filed && (
          <span className="flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-xs font-bold text-red-700">
            <Flag className="h-3.5 w-3.5" /> SAR Filed
          </span>
        )}
      </div>

      {/* Success banner */}
      {decisionSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 flex items-center gap-2">
          <CheckCircle className="h-4 w-4 text-emerald-600" />
          <p className="text-sm font-semibold text-emerald-800">{decisionSuccess}</p>
        </div>
      )}
      {rescreenResult && (
        <div className="rounded-lg border border-teal-200 bg-teal-50 p-3">
          <p className="text-sm font-semibold text-teal-800">{rescreenResult.message}</p>
          {rescreenResult.score !== undefined && (
            <p className="text-xs text-teal-700 mt-0.5">Score: {rescreenResult.score?.toFixed(1)} · Tier: {rescreenResult.tier} · Decision: {rescreenResult.decision}</p>
          )}
        </div>
      )}

      {/* Action Bar */}
      <div className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-white p-4 flex-wrap">
        <p className="text-sm font-semibold text-zinc-700 mr-2">Record Decision:</p>
        {(Object.entries(DECISION_CONFIG) as [keyof typeof DECISION_CONFIG, typeof DECISION_CONFIG[keyof typeof DECISION_CONFIG]][]).map(([key, cfg]) => {
          const Icon = cfg.icon;
          return (
            <button
              key={key}
              onClick={() => { setDecisionMode(key); setDecisionError(""); }}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold text-white transition-colors ${cfg.bg}`}
            >
              <Icon className="h-4 w-4" /> {cfg.label}
            </button>
          );
        })}
        <div className="ml-auto">
          <button
            onClick={handleRescreen}
            disabled={rescreening}
            className="flex items-center gap-1.5 rounded-lg border border-teal-200 bg-teal-50 px-4 py-2 text-sm font-semibold text-teal-700 hover:bg-teal-100 transition-colors disabled:opacity-60"
          >
            <Zap className={`h-4 w-4 ${rescreening ? "animate-pulse" : ""}`} />
            {rescreening ? "Rescreening…" : "Run AML Screening"}
          </button>
        </div>
      </div>

      {/* Decision Modal */}
      {decisionMode && (
        <div className="rounded-xl border-2 border-zinc-300 bg-white p-5 shadow-lg space-y-4">
          <h3 className="font-bold text-zinc-900">Decision: {DECISION_CONFIG[decisionMode].label}</h3>
          {decisionError && <p className="text-sm text-red-600">{decisionError}</p>}
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-600 mb-1">Notes * (required)</label>
              <textarea
                rows={4}
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                placeholder="Document your analysis and reasoning…"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-600 mb-1">Reason (optional)</label>
              <input
                type="text"
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                placeholder="Brief reason code or reference…"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={sarFiled} onChange={(e) => setSarFiled(e.target.checked)} className="rounded text-red-600" />
              <span className="text-sm font-semibold text-red-700">File a Suspicious Activity Report (SAR)</span>
            </label>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleDecision}
              disabled={submitting}
              className="rounded-lg bg-teal-600 px-5 py-2 text-sm font-bold text-white hover:bg-teal-700 disabled:opacity-60 transition-colors"
            >
              {submitting ? "Submitting…" : "Submit Decision"}
            </button>
            <button
              onClick={() => setDecisionMode(null)}
              className="rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-2 gap-5">
        {/* Customer */}
        <Section title="Customer Profile" icon={User} expanded={expanded.customer} onToggle={() => toggle("customer")}>
          {customer ? (
            <dl className="space-y-2">
              {[
                ["Name", `${customer.first_name ?? ""} ${customer.last_name ?? ""}`.trim() || "—"],
                ["Type", customer.customer_type],
                ["Nationality", customer.nationality ?? "—"],
                ["Country", customer.country ?? "—"],
                ["Status", customer.status],
              ].map(([l, v]) => (
                <div key={l} className="flex justify-between text-sm">
                  <dt className="text-zinc-500">{l}</dt>
                  <dd className="font-medium text-zinc-900 text-right">{v}</dd>
                </div>
              ))}
            </dl>
          ) : <p className="text-sm text-zinc-400">No customer data.</p>}
        </Section>

        {/* KYC */}
        <Section title="KYC Profile" icon={FileText} expanded={expanded.kyc} onToggle={() => toggle("kyc")}>
          {kyc_profile ? (
            <dl className="space-y-2">
              {[
                ["Full Name", kyc_profile.full_name],
                ["Occupation", kyc_profile.occupation ?? "—"],
                ["Source of Funds", kyc_profile.source_of_funds],
                ["Tax Residency", kyc_profile.tax_residency ?? "—"],
                ["Risk Category", kyc_profile.risk_category],
                ["Income Range", kyc_profile.annual_income_range ?? "—"],
              ].map(([l, v]) => (
                <div key={l} className="flex justify-between text-sm">
                  <dt className="text-zinc-500">{l}</dt>
                  <dd className={`font-medium text-right ${l === "Risk Category" ? (v === "high" ? "text-red-600" : v === "medium" ? "text-amber-600" : "text-emerald-600") : "text-zinc-900"}`}>{v}</dd>
                </div>
              ))}
            </dl>
          ) : <p className="text-sm text-zinc-400">No KYC profile.</p>}
        </Section>

        {/* Risk Score */}
        <Section title="Latest Risk Score" icon={Shield} expanded={expanded.risk} onToggle={() => toggle("risk")}>
          {latestRisk ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-4xl font-black text-zinc-900">{latestRisk.overall_score.toFixed(1)}</p>
                  <p className="text-xs text-zinc-400">/100</p>
                </div>
                <span className={`rounded-full px-4 py-2 text-sm font-bold uppercase ${latestRisk.risk_tier === "high" ? "text-red-700 bg-red-100" : latestRisk.risk_tier === "medium" ? "text-amber-700 bg-amber-100" : "text-emerald-700 bg-emerald-100"}`}>
                  {latestRisk.risk_tier}
                </span>
              </div>
              {latestRisk.breakdown && (
                <div className="space-y-1.5 pt-2 border-t border-zinc-100">
                  {Object.entries(latestRisk.breakdown).map(([agent, score]) => (
                    <div key={agent} className="flex items-center gap-2">
                      <span className="text-xs text-zinc-500 w-32 shrink-0">{agent.replace("_agent", "").replace("_", " ")}</span>
                      <div className="flex-1 bg-zinc-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${Number(score) >= 70 ? "bg-red-400" : Number(score) >= 40 ? "bg-amber-400" : "bg-emerald-400"}`}
                          style={{ width: `${Math.min(Number(score), 100)}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-zinc-700 w-8 text-right">{Number(score).toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : <p className="text-sm text-zinc-400">No risk score available.</p>}
        </Section>

        {/* Alerts */}
        <Section title={`Alerts (${alerts.length})`} icon={AlertTriangle} expanded={expanded.alerts} onToggle={() => toggle("alerts")}>
          {alerts.length ? (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {alerts.map((a) => (
                <div key={a.id} className={`rounded-lg border p-3 ${a.risk_score >= 90 ? "border-red-200 bg-red-50" : a.risk_score >= 75 ? "border-orange-200 bg-orange-50" : "border-zinc-200 bg-zinc-50"}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-zinc-700">{a.alert_type.replace(/_/g, " ")}</span>
                    <span className={`text-xs font-black ${a.risk_score >= 90 ? "text-red-600" : a.risk_score >= 75 ? "text-orange-500" : "text-amber-500"}`}>
                      {a.risk_score.toFixed(0)}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-600">
                    {(a.alert_metadata as Record<string, string>)?.detail ?? "Suspicious activity."}
                  </p>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-zinc-400">No alerts.</p>}
        </Section>
      </div>

      {/* Investigation Notes */}
      <Section title="Investigation Notes" icon={ClipboardList} expanded={expanded.notes} onToggle={() => toggle("notes")}>
        <pre className="whitespace-pre-wrap text-sm text-zinc-700 font-sans leading-relaxed">
          {c.investigation_notes || "No notes yet."}
        </pre>
      </Section>

      {/* Documents */}
      <Section title={`Documents (${documents.length})`} icon={FileText} expanded={expanded.documents} onToggle={() => toggle("documents")}>
        {documents.length ? (
          <div className="grid grid-cols-2 gap-2">
            {documents.map((d) => (
              <div key={d.id} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <p className="text-xs font-semibold text-zinc-700 capitalize">{d.document_type.replace("_", " ")}</p>
                <p className="text-xs text-zinc-500 truncate mt-0.5">{d.file_name}</p>
                <span className={`mt-1 inline-flex text-xs font-semibold ${d.verification_status === "verified" ? "text-emerald-600" : "text-amber-600"}`}>
                  {d.verification_status}
                </span>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-zinc-400">No documents uploaded.</p>}
      </Section>

      {/* Agent Logs */}
      <Section title={`AI Agent Logs (${agent_logs.length})`} icon={Bot} expanded={expanded.agents} onToggle={() => toggle("agents")}>
        {agent_logs.length ? (
          <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {agent_logs.map((log, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-teal-700">{log.agent_name}</span>
                  {log.execution_time_ms && (
                    <span className="text-xs text-zinc-400">{log.execution_time_ms}ms</span>
                  )}
                </div>
                <p className="text-xs text-zinc-500">{log.step_name}</p>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-zinc-400">No agent logs.</p>}
      </Section>
    </div>
  );
}

// ─── Reusable Section Component ────────────────────────────────────────────────

function Section({
  title, icon: Icon, expanded, onToggle, children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-teal-600" />
          <span className="text-sm font-bold text-zinc-900">{title}</span>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
      </button>
      {expanded && (
        <div className="border-t border-zinc-100 px-5 py-4">
          {children}
        </div>
      )}
    </div>
  );
}
