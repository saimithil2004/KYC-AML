"use client";

import React, { useEffect, useState } from "react";
import {
  RefreshCw, Play, XOctagon, Search, Filter, ShieldAlert,
  CheckCircle, AlertTriangle, PlayCircle, Clock, TrendingUp, TrendingDown,
  ArrowRight, ShieldCheck, ChevronLeft, ChevronRight, Activity
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  listMonitoringSchedules,
  listMonitoringHistory,
  listMonitoringJobs,
  triggerManualRescreen,
  retryFailedJob,
  cancelJob,
  getMonitoringStatistics
} from "@/lib/api";
import {
  MonitoringSchedule,
  MonitoringHistory,
  MonitoringJob,
  MonitoringStatistics
} from "@/lib/types";

export default function MonitoringHub() {
  const { user } = useAuth();
  const token = localStorage.getItem("token") || "";

  // Statistics
  const [stats, setStats] = useState<MonitoringStatistics | null>(null);

  // Active Tab
  const [activeTab, setActiveTab] = useState<"overview" | "schedules" | "queue" | "history">("overview");

  // State Lists
  const [schedules, setSchedules] = useState<MonitoringSchedule[]>([]);
  const [history, setHistory] = useState<MonitoringHistory[]>([]);
  const [jobs, setJobs] = useState<MonitoringJob[]>([]);

  // Page, filter & search
  const [page, setPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Loading/Action indicators
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [manualCustomerId, setManualCustomerId] = useState("");

  // Fetch statistics and list data based on tab
  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Get statistics
      const s = await getMonitoringStatistics(token);
      setStats(s);

      // 2. Fetch list based on active tab
      if (activeTab === "schedules") {
        const res = await listMonitoringSchedules(token, { page, page_size: 15, status: statusFilter || undefined });
        setSchedules(res.items);
        setTotalItems(res.total);
      } else if (activeTab === "queue") {
        const res = await listMonitoringJobs(token, { page, page_size: 15, status: statusFilter || undefined });
        setJobs(res.items);
        setTotalItems(res.total);
      } else if (activeTab === "history") {
        const res = await listMonitoringHistory(token, { page, page_size: 15, customer_id: searchQuery || undefined });
        setHistory(res.items);
        setTotalItems(res.total);
      }
    } catch (err: any) {
      console.error(err);
      setMessage({ type: "error", text: "Failed to fetch monitoring data." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab, page, statusFilter]);

  // Actions
  const handleTriggerScreening = async (customerId: string) => {
    if (!customerId.trim()) return;
    setLoading(true);
    setMessage(null);
    try {
      await triggerManualRescreen(customerId, token);
      setMessage({ type: "success", text: "Manual re-screening job triggered successfully!" });
      setManualCustomerId("");
      fetchData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to trigger re-screening." });
    } finally {
      setLoading(false);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    setLoading(true);
    setMessage(null);
    try {
      await retryFailedJob(jobId, token);
      setMessage({ type: "success", text: "Failed job queued for retry successfully." });
      fetchData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to retry job." });
    } finally {
      setLoading(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    setLoading(true);
    setMessage(null);
    try {
      await cancelJob(jobId, token);
      setMessage({ type: "success", text: "Job cancelled successfully." });
      fetchData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to cancel job." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Re-screening & Continuous Monitoring</h1>
          <p className="text-sm text-zinc-500">
            Real-time triggers, background Celery queue, and automated compliance review cycles.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 text-zinc-500 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Alert Messaging */}
      {message && (
        <div
          className={`flex items-center gap-3 p-4 rounded-lg text-sm font-medium ${
            message.type === "success"
              ? "bg-teal-50 border border-teal-100 text-teal-800"
              : "bg-rose-50 border border-rose-100 text-rose-800"
          }`}
        >
          {message.type === "success" ? <ShieldCheck className="h-5 w-5 text-teal-600" /> : <ShieldAlert className="h-5 w-5 text-rose-600" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Top statistics overview dashboard widgets (Part 10) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Under Monitoring</span>
            <Activity className="h-5 w-5 text-indigo-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">
              {stats?.customers_under_monitoring ?? 0}
            </span>
            <span className="text-xs text-zinc-500">active customers</span>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Today's Screenings</span>
            <CheckCircle className="h-5 w-5 text-teal-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">
              {stats?.todays_screenings ?? 0}
            </span>
            <span className="text-xs text-zinc-500">runs executed</span>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Risk Changes Today</span>
            <TrendingUp className="h-5 w-5 text-amber-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">
              {stats?.risk_changes_today ?? 0}
            </span>
            <span className="text-xs text-zinc-500">deltas logged</span>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Pending Review / Jobs</span>
            <Clock className="h-5 w-5 text-rose-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">
              {((stats?.queued_jobs ?? 0) + (stats?.running_jobs ?? 0)) || 0}
            </span>
            <span className="text-xs text-zinc-500">
              ({stats?.failed_jobs ?? 0} failed)
            </span>
          </div>
        </div>
      </div>

      {/* Manual Rescreen trigger section */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h3 className="font-bold text-zinc-900 text-sm">Force Manual Customer Recheck</h3>
          <p className="text-xs text-zinc-500">Queue an immediate complete compliance re-screening against active lists.</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <input
            type="text"
            placeholder="Enter Customer UUID"
            value={manualCustomerId}
            onChange={(e) => setManualCustomerId(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs focus:outline-none focus:border-teal-500"
          />
          <button
            onClick={() => handleTriggerScreening(manualCustomerId)}
            disabled={loading || !manualCustomerId.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 transition-colors disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            Run screening
          </button>
        </div>
      </div>

      {/* TABS SELECTOR */}
      <div className="flex border-b border-zinc-200">
        <button
          onClick={() => { setActiveTab("overview"); setPage(1); }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors ${
            activeTab === "overview"
              ? "border-teal-600 text-teal-600 font-bold"
              : "border-transparent text-zinc-500 hover:text-zinc-800"
          }`}
        >
          System Overview
        </button>
        <button
          onClick={() => { setActiveTab("schedules"); setPage(1); }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors ${
            activeTab === "schedules"
              ? "border-teal-600 text-teal-600 font-bold"
              : "border-transparent text-zinc-500 hover:text-zinc-800"
          }`}
        >
          Scheduled Reviews ({stats?.upcoming_reviews ?? 0} due)
        </button>
        <button
          onClick={() => { setActiveTab("queue"); setPage(1); }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors ${
            activeTab === "queue"
              ? "border-teal-600 text-teal-600 font-bold"
              : "border-transparent text-zinc-500 hover:text-zinc-800"
          }`}
        >
          Celery Queue Status ({stats?.queued_jobs ?? 0} queued)
        </button>
        <button
          onClick={() => { setActiveTab("history"); setPage(1); }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors ${
            activeTab === "history"
              ? "border-teal-600 text-teal-600 font-bold"
              : "border-transparent text-zinc-500 hover:text-zinc-800"
          }`}
        >
          Screening History logs
        </button>
      </div>

      {/* CONTENT LISTINGS */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden shadow-sm">
        
        {/* OVERVIEW TAB CONTENT */}
        {activeTab === "overview" && (
          <div className="p-6 space-y-6">
            <h3 className="font-bold text-zinc-900 text-sm">Background Worker Celery Beat Configuration</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-zinc-100 bg-zinc-50 p-4 space-y-2">
                <h4 className="font-semibold text-xs text-zinc-800 uppercase tracking-wider">Scheduled Cron Jobs</h4>
                <ul className="space-y-2.5 text-xs text-zinc-600">
                  <li className="flex justify-between border-b border-zinc-200 pb-1.5">
                    <span>Daily Monitoring</span>
                    <span className="text-zinc-400 font-mono">0 0 * * *</span>
                  </li>
                  <li className="flex justify-between border-b border-zinc-200 pb-1.5">
                    <span>Weekly Reviews</span>
                    <span className="text-zinc-400 font-mono">0 0 * * 0</span>
                  </li>
                  <li className="flex justify-between border-b border-zinc-200 pb-1.5">
                    <span>PEP & Sanctions Sync</span>
                    <span className="text-zinc-400 font-mono">*/30 * * * *</span>
                  </li>
                  <li className="flex justify-between">
                    <span>Retry Failed Screenings</span>
                    <span className="text-zinc-400 font-mono">*/15 * * * *</span>
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-zinc-100 bg-zinc-50 p-4 space-y-3">
                <h4 className="font-semibold text-xs text-zinc-800 uppercase tracking-wider">Change Detection triggers</h4>
                <div className="grid grid-cols-2 gap-2 text-xs text-zinc-600">
                  <div className="flex items-center gap-1.5 bg-white border border-zinc-150 p-2 rounded-md">
                    <div className="h-2 w-2 rounded-full bg-teal-500" />
                    Profile Updates
                  </div>
                  <div className="flex items-center gap-1.5 bg-white border border-zinc-150 p-2 rounded-md">
                    <div className="h-2 w-2 rounded-full bg-teal-500" />
                    New Document Uploads
                  </div>
                  <div className="flex items-center gap-1.5 bg-white border border-zinc-150 p-2 rounded-md">
                    <div className="h-2 w-2 rounded-full bg-teal-500" />
                    Transaction Anomalies
                  </div>
                  <div className="flex items-center gap-1.5 bg-white border border-zinc-150 p-2 rounded-md">
                    <div className="h-2 w-2 rounded-full bg-teal-500" />
                    Regulatory changes
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SCHEDULES TAB CONTENT */}
        {activeTab === "schedules" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-50 border-b border-zinc-200 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  <th className="p-4">Customer ID</th>
                  <th className="p-4">Next Review Target</th>
                  <th className="p-4">Frequency</th>
                  <th className="p-4">Last review date</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-xs text-zinc-700">
                {schedules.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-zinc-400">
                      No active review schedules found.
                    </td>
                  </tr>
                ) : (
                  schedules.map((s) => (
                    <tr key={s.id} className="hover:bg-zinc-50">
                      <td className="p-4 font-mono">{s.customer_id}</td>
                      <td className="p-4 font-semibold text-zinc-950">{s.next_review_date}</td>
                      <td className="p-4">{s.review_frequency_months} months</td>
                      <td className="p-4 text-zinc-500">{s.last_review_date || "Never"}</td>
                      <td className="p-4">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          s.status === "scheduled"
                            ? "bg-teal-50 text-teal-700 border border-teal-100"
                            : "bg-amber-50 text-amber-700 border border-amber-100"
                        }`}>
                          {s.status}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <button
                          onClick={() => handleTriggerScreening(s.customer_id)}
                          className="inline-flex items-center gap-1 rounded bg-teal-600 px-2 py-1 text-[11px] font-semibold text-white hover:bg-teal-700"
                        >
                          <Play className="h-3 w-3" /> Run now
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* QUEUE TAB CONTENT */}
        {activeTab === "queue" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-50 border-b border-zinc-200 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  <th className="p-4">Job ID</th>
                  <th className="p-4">Customer ID</th>
                  <th className="p-4">Trigger</th>
                  <th className="p-4">Retries</th>
                  <th className="p-4">Worker</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-xs text-zinc-700">
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-zinc-400">
                      No active Celery tasks in queue.
                    </td>
                  </tr>
                ) : (
                  jobs.map((j) => (
                    <tr key={j.id} className="hover:bg-zinc-50">
                      <td className="p-4 font-mono">{j.id.slice(0, 8)}...</td>
                      <td className="p-4 font-mono">{j.customer_id}</td>
                      <td className="p-4 font-semibold text-zinc-800">{j.trigger_reason}</td>
                      <td className="p-4">{j.retry_count}</td>
                      <td className="p-4 text-zinc-400 font-mono">{j.worker_name || "pending"}</td>
                      <td className="p-4">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          j.status === "completed"
                            ? "bg-teal-50 text-teal-700 border border-teal-100"
                            : j.status === "running"
                            ? "bg-indigo-50 text-indigo-700 border border-indigo-100"
                            : j.status === "failed"
                            ? "bg-rose-50 text-rose-700 border border-rose-100"
                            : "bg-zinc-100 text-zinc-700"
                        }`}>
                          {j.status}
                        </span>
                      </td>
                      <td className="p-4 text-right space-x-1.5">
                        {j.status === "failed" && (
                          <button
                            onClick={() => handleRetryJob(j.id)}
                            className="inline-flex items-center gap-1 rounded bg-amber-600 px-2 py-1 text-[11px] font-semibold text-white hover:bg-amber-700"
                          >
                            Retry
                          </button>
                        )}
                        {(j.status === "queued" || j.status === "running") && (
                          <button
                            onClick={() => handleCancelJob(j.id)}
                            className="inline-flex items-center gap-1 rounded bg-rose-600 px-2 py-1 text-[11px] font-semibold text-white hover:bg-rose-700"
                          >
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* HISTORY TAB CONTENT */}
        {activeTab === "history" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-50 border-b border-zinc-200 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  <th className="p-4">Run Date</th>
                  <th className="p-4">Trigger</th>
                  <th className="p-4">Old / New Score</th>
                  <th className="p-4">Risk Delta</th>
                  <th className="p-4">Trend</th>
                  <th className="p-4">Old / New Decision</th>
                  <th className="p-4 text-right">Execution Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-xs text-zinc-700">
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-zinc-400">
                      No screening history entries logged.
                    </td>
                  </tr>
                ) : (
                  history.map((h) => (
                    <tr key={h.id} className="hover:bg-zinc-50">
                      <td className="p-4 text-zinc-500">
                        {new Date(h.screening_date).toLocaleString()}
                      </td>
                      <td className="p-4 font-semibold text-zinc-800">{h.trigger_reason}</td>
                      <td className="p-4">
                        <span className="text-zinc-400">{h.old_score}</span>
                        <ArrowRight className="inline-block h-3 w-3 mx-1 text-zinc-400" />
                        <span className="font-semibold">{h.new_score}</span>
                      </td>
                      <td className="p-4">
                        <span className={`font-semibold ${h.risk_delta > 0 ? "text-rose-600" : h.risk_delta < 0 ? "text-teal-600" : "text-zinc-400"}`}>
                          {h.risk_delta > 0 ? `+${h.risk_delta.toFixed(1)}` : h.risk_delta.toFixed(1)}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`inline-flex items-center gap-1 font-bold ${
                          h.risk_trend === "deteriorating"
                            ? "text-rose-600"
                            : h.risk_trend === "improving"
                            ? "text-teal-600"
                            : "text-zinc-500"
                        }`}>
                          {h.risk_trend === "deteriorating" ? <TrendingUp className="h-3.5 w-3.5" /> : h.risk_trend === "improving" ? <TrendingDown className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
                          {h.risk_trend}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className="text-zinc-400">{h.old_decision}</span>
                        <ArrowRight className="inline-block h-3 w-3 mx-1 text-zinc-400" />
                        <span className="font-semibold">{h.new_decision}</span>
                      </td>
                      <td className="p-4 text-right font-mono text-zinc-500">
                        {h.execution_time_ms} ms
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* PAGINATION CONTROLS */}
        {activeTab !== "overview" && totalItems > 15 && (
          <div className="flex items-center justify-between border-t border-zinc-200 bg-white px-4 py-3 sm:px-6">
            <div className="flex flex-1 justify-between sm:hidden">
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page === 1}
                className="relative inline-flex items-center rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * 15 >= totalItems}
                className="relative ml-3 inline-flex items-center rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                Next
              </button>
            </div>
            <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
              <div>
                <p className="text-xs text-zinc-700">
                  Showing page <span className="font-bold">{page}</span> of{" "}
                  <span className="font-bold">{Math.ceil(totalItems / 15)}</span> (Total: <span className="font-bold">{totalItems}</span> items)
                </p>
              </div>
              <div>
                <nav className="isolate inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination">
                  <button
                    onClick={() => setPage((p) => Math.max(p - 1, 1))}
                    disabled={page === 1}
                    className="relative inline-flex items-center rounded-l-md px-2 py-2 text-zinc-400 ring-1 ring-inset ring-zinc-300 hover:bg-zinc-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page * 15 >= totalItems}
                    className="relative inline-flex items-center rounded-r-md px-2 py-2 text-zinc-400 ring-1 ring-inset ring-zinc-300 hover:bg-zinc-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </nav>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
