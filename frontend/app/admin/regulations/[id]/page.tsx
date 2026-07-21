"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  getRegulation,
  extractRulesFromRegulation,
  listRegulationVersions,
  rollbackRegulation,
} from "@/lib/api";
import type { Regulation, PolicyRule, RegulationVersion } from "@/lib/types";
import {
  BookOpen, Sliders, RefreshCw, FileText, ArrowLeft, Bot, Sparkles, CheckCircle,
  AlertTriangle, RotateCcw, ShieldCheck, Clock, User, MessageSquare, Info,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

export default function RegulationDetailsPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [activeSubTab, setActiveSubTab] = useState("metadata");
  const [regulation, setRegulation] = useState<Regulation | null>(null);
  const [versions, setVersions] = useState<RegulationVersion[]>([]);
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractSuccess, setExtractSuccess] = useState("");

  // Rollback dialog
  const [rollbackOpen, setRollbackOpen] = useState(false);
  const [rollbackVersionId, setRollbackVersionId] = useState("");
  const [rollbackVersionName, setRollbackVersionName] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");
  const [rollingBack, setRollingBack] = useState(false);
  const [rollbackError, setRollbackError] = useState("");

  const loadData = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    try {
      const reg = await getRegulation(id, token);
      setRegulation(reg);
      const vers = await listRegulationVersions(id, token);
      setVersions(vers);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Extract rules callback
  const handleExtractRules = async () => {
    if (!token || !id) return;
    setExtracting(true);
    setExtractSuccess("");
    try {
      const newRules = await extractRulesFromRegulation(id, token);
      setRules(newRules);
      setExtractSuccess(`Successfully extracted ${newRules.length} policy rules!`);
      // Reload versions as extraction updates snapshot
      const vers = await listRegulationVersions(id, token);
      setVersions(vers);
    } catch (err) {
      console.error(err);
    } finally {
      setExtracting(false);
    }
  };

  // Rollback trigger
  const handleRollbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !id || !rollbackVersionId || !rollbackReason) return;
    setRollingBack(true);
    setRollbackError("");
    try {
      await rollbackRegulation(id, rollbackVersionId, rollbackReason, token);
      setRollbackOpen(false);
      setRollbackReason("");
      loadData();
    } catch (err: any) {
      setRollbackError(err.message || "Failed to rollback version");
    } finally {
      setRollingBack(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-24">
        <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (!regulation) {
    return (
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-8 text-center text-zinc-400">
        <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-rose-500" />
        <p className="text-sm">Regulation not found.</p>
        <Link href="/admin/regulations" className="text-xs text-teal-600 underline mt-2 inline-block">
          Back to Regulations
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in text-zinc-800 dark:text-zinc-200">
      {/* Back button */}
      <div className="flex items-center gap-2">
        <Link
          href="/admin/regulations"
          className="flex items-center gap-1 text-xs font-bold text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Regulations
        </Link>
      </div>

      {/* Header Info */}
      <div className="flex items-start justify-between flex-wrap gap-4 border-b pb-4 dark:border-zinc-800">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              {regulation.title}
            </h1>
            <span className="text-[10px] bg-zinc-150 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded px-2 py-0.5">
              v{regulation.version}
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            Jurisdiction: <span className="font-bold text-zinc-650 dark:text-zinc-300">{regulation.jurisdiction || "Global"}</span> · Country: <span className="font-bold text-zinc-650 dark:text-zinc-300">{regulation.country || "All"}</span> · Authority: <span className="font-bold text-zinc-650 dark:text-zinc-300">{regulation.authority}</span>
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={handleExtractRules}
            disabled={extracting}
            className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-bold text-white hover:bg-teal-700 transition shadow-sm disabled:opacity-50"
          >
            <Bot className="h-4 w-4" />
            {extracting ? "Running AI rules extraction…" : "Extract Rules with Gemini"}
          </button>
        )}
      </div>

      {/* Success Notification */}
      {extractSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 p-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0" />
          <p className="text-xs font-semibold text-emerald-800 dark:text-emerald-400">{extractSuccess}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-zinc-200 dark:border-zinc-800 gap-1 pb-px text-xs">
        {[
          { id: "metadata", label: "Metadata info", icon: Info },
          { id: "extracted", label: "Extracted Document Plain Text", icon: FileText },
          { id: "rules", label: "Generated Rules Preview", icon: Sliders },
          { id: "versions", label: "Version history & Rollback", icon: RotateCcw },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveSubTab(tab.id);
                setExtractSuccess("");
              }}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-bold transition ${
                isActive
                  ? "border-teal-600 text-teal-600"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 hover:border-zinc-200"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      {activeSubTab === "metadata" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
          <div className="col-span-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
            <h3 className="font-bold text-zinc-900 dark:text-white uppercase tracking-wider text-[10px]">
              Regulation Scope & Target Scope
            </h3>
            <p className="text-zinc-600 dark:text-zinc-450 leading-relaxed text-sm">
              {regulation.description || "No description provided."}
            </p>
            <div className="grid grid-cols-2 gap-4 border-t dark:border-zinc-800 pt-4">
              <div>
                <span className="text-[10px] text-zinc-400 font-bold uppercase">Effective Date</span>
                <p className="font-mono text-zinc-800 dark:text-zinc-200">{regulation.effective_date || "—"}</p>
              </div>
              <div>
                <span className="text-[10px] text-zinc-400 font-bold uppercase">Expiry Date</span>
                <p className="font-mono text-zinc-800 dark:text-zinc-200">{regulation.expiry_date || "—"}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
            <h3 className="font-bold text-zinc-900 dark:text-white uppercase tracking-wider text-[10px]">
              Ingestion Metadata
            </h3>
            <div className="space-y-3">
              <div>
                <span className="text-[10px] text-zinc-400 font-bold uppercase block">Original File Name</span>
                <span className="text-zinc-800 dark:text-zinc-200 truncate block">
                  {String((regulation.document_metadata as any)?.original_filename || "Original Document")}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-zinc-400 font-bold uppercase block">Storage Size</span>
                <span className="text-zinc-800 dark:text-zinc-200 font-mono block">
                  {(regulation.document_metadata as any)?.size
                    ? `${(Number((regulation.document_metadata as any).size) / 1024).toFixed(1)} KB`
                    : "—"}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-zinc-400 font-bold uppercase block">Storage File Path</span>
                <span className="text-zinc-800 dark:text-zinc-200 font-mono block truncate" title={regulation.upload_path}>
                  {regulation.upload_path}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeSubTab === "extracted" && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
          <h3 className="font-bold text-zinc-900 dark:text-white uppercase tracking-wider text-[10px]">
            Extracted Plain Text Preview
          </h3>
          <pre className="p-4 bg-zinc-50 dark:bg-zinc-950/20 border border-zinc-150 dark:border-zinc-800 rounded-lg max-h-[500px] overflow-y-auto font-mono text-[11px] whitespace-pre-wrap leading-relaxed text-zinc-700 dark:text-zinc-300">
            {regulation.extracted_text || "No text extracted."}
          </pre>
        </div>
      )}

      {activeSubTab === "rules" && (
        <div className="space-y-4 text-xs">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-zinc-900 dark:text-white uppercase tracking-wider text-[10px]">
              Rules snapshot for Regulation (v{regulation.version})
            </h3>
            <Link
              href="/admin/policy-rules"
              className="text-xs font-semibold text-teal-600 hover:underline"
            >
              Go to Policy Rules Console →
            </Link>
          </div>

          {/* List generated rules */}
          {rules.length === 0 ? (
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-8 text-center text-zinc-400">
              <Bot className="h-7 w-7 mx-auto mb-2 text-zinc-350" />
              <p>No policy rules generated yet.</p>
              {isAdmin && (
                <button
                  onClick={handleExtractRules}
                  disabled={extracting}
                  className="mt-3 text-xs font-bold bg-teal-50 dark:bg-teal-950/20 text-teal-700 px-3 py-1.5 rounded border border-teal-200 hover:bg-teal-100 transition"
                >
                  Run Rule Extractor
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {rules.map((rule) => (
                <div key={rule.id} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 space-y-2.5">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-zinc-900 dark:text-white">{rule.rule_name}</span>
                      <span className="rounded bg-teal-50 dark:bg-teal-950/20 text-teal-700 px-1.5 py-0.5 font-bold text-[10px] uppercase">
                        {rule.rule_type}
                      </span>
                      <span className="rounded bg-rose-50 dark:bg-rose-950/20 text-rose-700 px-1.5 py-0.5 font-bold text-[10px] uppercase">
                        {rule.severity}
                      </span>
                    </div>
                  </div>
                  <p className="text-zinc-650 dark:text-zinc-400">{rule.description || "No rule description."}</p>
                  <div className="p-2.5 bg-zinc-50 dark:bg-zinc-950/20 border border-zinc-150 dark:border-zinc-850 rounded font-mono text-[10px] text-zinc-600 dark:text-zinc-300">
                    <span className="font-bold text-teal-600">Conditions: </span>
                    {JSON.stringify(rule.conditions)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeSubTab === "versions" && (
        <div className="space-y-4 text-xs">
          <h3 className="font-bold text-zinc-900 dark:text-white uppercase tracking-wider text-[10px]">
            Version Snapshot Registry
          </h3>

          <div className="space-y-3">
            {versions.map((ver) => (
              <div
                key={ver.id}
                className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex items-start gap-4 hover:shadow-sm transition"
              >
                <div className="p-2.5 bg-zinc-50 dark:bg-zinc-950/20 border border-zinc-150 dark:border-zinc-800 rounded shrink-0">
                  <Clock className="h-4.5 w-4.5 text-zinc-500" />
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-zinc-850 dark:text-zinc-200">Version {ver.version}</span>
                    <span className="text-[10px] text-zinc-450">
                      {new Date(ver.created_at).toLocaleString("en-GB")}
                    </span>
                  </div>
                  <p className="text-zinc-600 dark:text-zinc-400 italic">
                    "{ver.change_description || "No description provided."}"
                  </p>
                  <p className="text-[10px] text-zinc-400 flex items-center gap-1">
                    <User className="h-3 w-3" /> Author ID: {ver.author_id || "System"}
                  </p>
                </div>
                {isAdmin && regulation.version !== ver.version && (
                  <button
                    onClick={() => {
                      setRollbackVersionId(ver.id);
                      setRollbackVersionName(ver.version);
                      setRollbackOpen(true);
                      setRollbackError("");
                    }}
                    className="shrink-0 text-xs font-bold text-teal-600 hover:text-teal-800 flex items-center gap-1 border border-teal-200 rounded px-2.5 py-1 hover:bg-teal-50 dark:hover:bg-teal-950/20"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Rollback
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rollback Dialog Confirmation Modal */}
      {rollbackOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-5 space-y-4 shadow-xl">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
              <RotateCcw className="text-teal-650 h-4.5 w-4.5" /> Rollback to Version {rollbackVersionName}
            </h3>

            {rollbackError && (
              <div className="p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 rounded-lg text-xs text-red-700">
                {rollbackError}
              </div>
            )}

            <form onSubmit={handleRollbackSubmit} className="space-y-4 text-xs">
              <p className="text-zinc-550 leading-relaxed">
                Warning: Rolling back will revert this regulation document and its active policy rules to this historical snapshot.
              </p>
              <div className="space-y-1">
                <label className="font-bold text-zinc-650 dark:text-zinc-400">Rollback Reason *</label>
                <textarea
                  required
                  rows={3}
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  placeholder="Explain why this version rollback is being performed..."
                  className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700 focus:border-teal-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setRollbackOpen(false)}
                  className="rounded border px-4 py-2 font-semibold hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rollingBack}
                  className="rounded bg-teal-600 hover:bg-teal-700 text-white font-bold px-6 py-2 disabled:opacity-50"
                >
                  {rollingBack ? "Restoring Snapshot…" : "Confirm Rollback"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
