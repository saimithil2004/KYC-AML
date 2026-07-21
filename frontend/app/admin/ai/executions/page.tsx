"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { getAIExecutions, getAIExecutionDetail, getAIExplanation, submitAIFeedback } from "@/lib/api";
import type { AIExecution, AIExplanation } from "@/lib/types";
import {
  History, Eye, Star, AlertTriangle, RefreshCw, X, MessageSquare,
  ShieldAlert, Send, FileJson, CheckCircle
} from "lucide-react";

export default function ExecutionExplorerPage() {
  const { token } = useAuth();
  const [executions, setExecutions] = useState<AIExecution[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  // Search/Filters
  const [customerIdFilter, setCustomerIdFilter] = useState("");

  // Inspect Overlay
  const [selectedExec, setSelectedExec] = useState<AIExecution | null>(null);
  const [selectedExplain, setSelectedExplain] = useState<AIExplanation | null>(null);
  const [showInspector, setShowInspector] = useState(false);

  // Feedback states
  const [rating, setRating] = useState(5);
  const [comments, setComments] = useState("");
  const [isCorrect, setIsCorrect] = useState(true);
  const [isHelpful, setIsHelpful] = useState(true);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setErrorMsg("");
      const res = await getAIExecutions(token, page, 20, customerIdFilter || undefined);
      setExecutions(res.results || []);
      setTotal(res.total || 0);
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to query execution logs.");
    } finally {
      setLoading(false);
    }
  }, [token, page, customerIdFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleInspect = async (id: string) => {
    if (!token) return;
    try {
      setErrorMsg("");
      setFeedbackSuccess(false);
      const [detailRes, explainRes] = await Promise.all([
        getAIExecutionDetail(token, id),
        getAIExplanation(token, id).catch(() => null) // Suppress if not exists
      ]);
      setSelectedExec(detailRes);
      setSelectedExplain(explainRes);
      setShowInspector(true);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load execution details.");
    }
  };

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedExec) return;
    try {
      await submitAIFeedback(token, {
        execution_id: selectedExec.id,
        rating,
        is_correct: isCorrect,
        is_helpful: isHelpful,
        comments
      });
      setFeedbackSuccess(true);
      setComments("");
      setRating(5);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit evaluation feedback.");
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-teal-600" />
        <span className="ml-3 text-sm text-zinc-600 font-semibold">Querying execution logs...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn text-xs">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white p-6 rounded-2xl shadow-sm border border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
            <History className="h-6 w-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">AI Execution Explorer</h1>
            <p className="text-xs text-zinc-400">Search execution logs, inspect agent reasoning trees, check costs, and submit human reviews feedback</p>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
          <AlertTriangle className="h-4.5 w-4.5 text-rose-500 shrink-0" />
          <p className="font-semibold">{errorMsg}</p>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-zinc-200 flex flex-wrap gap-4 items-center">
        <div className="flex-1 min-w-[240px]">
          <input
            type="text"
            placeholder="Search by Customer ID (UUID format)..."
            value={customerIdFilter}
            onChange={(e) => setCustomerIdFilter(e.target.value)}
            className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
          />
        </div>
        <button
          onClick={() => { setPage(1); loadData(); }}
          className="px-4 py-2 bg-zinc-900 hover:bg-zinc-850 text-white font-bold rounded-lg transition-colors"
        >
          Apply Filters
        </button>
      </div>

      {/* Executions Table */}
      <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-zinc-700">
            <thead>
              <tr className="text-zinc-450 border-b border-zinc-150 uppercase text-[10px] font-bold">
                <th className="pb-3">Execution ID</th>
                <th className="pb-3">Subject ID</th>
                <th className="pb-3 text-right">Latency</th>
                <th className="pb-3 text-right">Tokens Count</th>
                <th className="pb-3 text-right">Estimated Cost</th>
                <th className="pb-3">Timestamp</th>
                <th className="pb-3 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((e) => (
                <tr key={e.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                  <td className="py-3 font-mono font-bold text-zinc-800">{e.id.substring(0, 8)}...</td>
                  <td className="py-3 font-mono text-zinc-500">{e.customer_id ? `${e.customer_id.substring(0, 13)}...` : "System"}</td>
                  <td className="py-3 text-right font-bold text-zinc-600 font-mono">{e.latency_ms} ms</td>
                  <td className="py-3 text-right font-mono text-zinc-500">{e.tokens_used.toLocaleString()}</td>
                  <td className="py-3 text-right font-mono font-bold text-teal-600">${e.cost.toFixed(5)}</td>
                  <td className="py-3 text-zinc-500 font-medium">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => handleInspect(e.id)}
                      className="p-1.5 border hover:bg-zinc-50 rounded-md transition-colors text-zinc-600 inline-flex items-center gap-1 font-bold"
                    >
                      <Eye className="h-3.5 w-3.5" /> View Details
                    </button>
                  </td>
                </tr>
              ))}
              {executions.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-zinc-400 font-medium">No execution history found. Run workflow screening agent checks to record executions.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex justify-between items-center text-zinc-500 pt-3 border-t">
          <span>Showing {executions.length} entries of {total} total</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(p - 1, 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border rounded-lg hover:bg-zinc-50 font-bold disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={executions.length < 20}
              className="px-3 py-1.5 border rounded-lg hover:bg-zinc-50 font-bold disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Inspect Detail Overlay Panel */}
      {showInspector && selectedExec && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-end">
          <div className="bg-white h-full max-w-2xl w-full p-6 shadow-2xl overflow-y-auto space-y-6 animate-slideInRight flex flex-col justify-between">
            <div className="space-y-6">
              <div className="flex justify-between items-center border-b pb-3">
                <div>
                  <h3 className="text-sm font-bold text-zinc-800 font-mono">Execution ID: {selectedExec.id}</h3>
                  <p className="text-[10px] text-zinc-400 font-semibold uppercase mt-0.5">Recorded: {new Date(selectedExec.created_at).toLocaleString()}</p>
                </div>
                <button onClick={() => setShowInspector(false)} className="text-zinc-400 hover:text-zinc-600">
                  <X className="h-4.5 w-4.5" />
                </button>
              </div>

              {/* Execution Prompt/Response Blobs */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <span className="font-bold text-zinc-500 flex items-center gap-1.5">
                    <FileJson className="h-4 w-4" /> Prompt Content context
                  </span>
                  <div className="bg-zinc-50 border rounded-lg p-3 font-mono overflow-auto max-h-40 text-zinc-700 text-[10px]">
                    {selectedExec.prompt_content}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <span className="font-bold text-zinc-500 flex items-center gap-1.5">
                    <FileJson className="h-4 w-4" /> Response Output payload
                  </span>
                  <div className="bg-zinc-50 border rounded-lg p-3 font-mono overflow-auto max-h-40 text-zinc-700 text-[10px]">
                    {selectedExec.response_content}
                  </div>
                </div>
              </div>

              {/* Explainability Report Block */}
              {selectedExplain && (
                <div className="space-y-3 bg-zinc-50 p-4 border rounded-xl">
                  <h4 className="font-bold text-zinc-800 flex items-center gap-1.5">
                    <ShieldAlert className="h-4 w-4 text-amber-500" /> Explainability Decision Report
                  </h4>
                  <div className="space-y-2 text-zinc-700">
                    <p><strong>Executive Summary:</strong> {selectedExplain.decision_summary}</p>
                    <p><strong>Confidence:</strong> {selectedExplain.confidence}%</p>
                    <p><strong>Matched Rules:</strong> {selectedExplain.matched_rules}</p>
                    <p><strong>Matched Entities:</strong> {selectedExplain.matched_entities}</p>
                    <p><strong>Actions Recommended:</strong> {selectedExplain.recommended_actions}</p>
                  </div>
                </div>
              )}

              {/* Human Feedback Loop Form */}
              <div className="border-t pt-4 space-y-4">
                <h4 className="font-bold text-zinc-800 flex items-center gap-1.5">
                  <MessageSquare className="h-4 w-4 text-teal-600" /> Submit Quality Verification Feedback
                </h4>
                {feedbackSuccess ? (
                  <div className="flex items-center gap-2 p-3 bg-emerald-50 text-emerald-800 rounded-lg font-bold border border-emerald-200">
                    <CheckCircle className="h-4 w-4 text-emerald-500" />
                    <span>Feedback successfully logged. Thank you!</span>
                  </div>
                ) : (
                  <form onSubmit={handleFeedbackSubmit} className="space-y-4 font-semibold text-zinc-700">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block mb-1">Audit Rating (1-5)</label>
                        <select
                          value={rating}
                          onChange={(e) => setRating(Number(e.target.value))}
                          className="w-full border rounded-lg p-2 focus:outline-teal-650 text-zinc-850 font-bold"
                        >
                          <option value="5">5 - Excellent</option>
                          <option value="4">4 - Good</option>
                          <option value="3">3 - Acceptable</option>
                          <option value="2">2 - Poor</option>
                          <option value="1">1 - Flagged / Buggy</option>
                        </select>
                      </div>
                      <div className="flex items-center gap-4 pt-5">
                        <label className="flex items-center gap-1.5">
                          <input type="checkbox" checked={isCorrect} onChange={(e) => setIsCorrect(e.target.checked)} />
                          Is Correct
                        </label>
                        <label className="flex items-center gap-1.5">
                          <input type="checkbox" checked={isHelpful} onChange={(e) => setIsHelpful(e.target.checked)} />
                          Is Helpful
                        </label>
                      </div>
                    </div>
                    <div>
                      <label className="block mb-1">Comments / Audit Notes</label>
                      <textarea
                        rows={2}
                        value={comments}
                        onChange={(e) => setComments(e.target.value)}
                        placeholder="Write manual evaluation details or override notes here..."
                        className="w-full border rounded-lg p-2.5 text-zinc-800 focus:outline-teal-600"
                      />
                    </div>
                    <button
                      type="submit"
                      className="w-full py-2 bg-zinc-950 text-white font-bold rounded-lg hover:bg-zinc-850 transition-colors flex items-center justify-center gap-1"
                    >
                      <Send className="h-3.5 w-3.5" /> Submit Audit Review
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
