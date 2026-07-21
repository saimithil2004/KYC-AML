"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { listAlerts, updateAlert } from "@/lib/api";
import type { Alert, Paginated } from "@/lib/types";
import {
  AlertTriangle, RefreshCw, ChevronLeft, ChevronRight,
  CheckCircle, Clock, XCircle, Search, Eye, TrendingUp,
} from "lucide-react";
import Link from "next/link";

const PAGE_SIZE = 20;

const ALERT_TYPE_LABELS: Record<string, string> = {
  LARGE_TRANSACTION: "Large Transaction",
  RAPID_TRANSACTIONS: "Rapid Transactions",
  STRUCTURING: "Structuring",
  DORMANT_REACTIVATION: "Dormant Account",
  CIRCULAR_TRANSFER: "Circular Transfer",
  REPEATED_BENEFICIARY: "Repeated Beneficiary",
  HIGH_RISK_COUNTRY: "High-Risk Country",
  VELOCITY_ANOMALY: "Velocity Anomaly",
  CASH_INTENSIVE: "Cash Intensive",
  MULE_INDICATOR: "Mule Indicator",
};

const STATUS_STYLES: Record<string, string> = {
  open: "text-red-700 bg-red-50 border-red-200",
  under_review: "text-amber-700 bg-amber-50 border-amber-200",
  escalated: "text-purple-700 bg-purple-50 border-purple-200",
  dismissed: "text-zinc-600 bg-zinc-100 border-zinc-200",
  closed: "text-emerald-700 bg-emerald-50 border-emerald-200",
};

const RISK_COLOR = (score: number) => {
  if (score >= 90) return "text-red-600";
  if (score >= 75) return "text-orange-500";
  if (score >= 50) return "text-amber-500";
  return "text-emerald-600";
};

export default function AlertsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Paginated<Alert> | null>(null);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listAlerts(token, {
        page,
        page_size: PAGE_SIZE,
        status: filterStatus || undefined,
        alert_type: filterType || undefined,
        sort_dir: "desc",
      });
      setData(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, page, filterStatus, filterType]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleStatusChange = async (alertId: string, newStatus: string) => {
    if (!token) return;
    setUpdating(alertId);
    try {
      await updateAlert(alertId, { status: newStatus }, token);
      fetchData();
    } catch (err) {
      console.error(err);
    } finally {
      setUpdating(null);
    }
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const openCount = data?.items.filter(a => a.status === "open").length ?? 0;
  const criticalCount = data?.items.filter(a => a.risk_score >= 90).length ?? 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Alert Management</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Triage and resolve AI-generated AML alerts</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Alerts", value: data?.total ?? 0, icon: AlertTriangle, color: "text-zinc-600" },
          { label: "Open", value: openCount, icon: Clock, color: "text-red-500" },
          { label: "Critical (≥90)", value: criticalCount, icon: TrendingUp, color: "text-red-600" },
          { label: "This Page", value: data?.items.length ?? 0, icon: Eye, color: "text-teal-600" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-zinc-200 bg-white p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-zinc-400">{stat.label}</p>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </div>
            <p className="text-2xl font-bold text-zinc-900">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Alert Types</option>
          {Object.entries(ALERT_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="under_review">Under Review</option>
          <option value="escalated">Escalated</option>
          <option value="dismissed">Dismissed</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {/* Alert Cards */}
      <div className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-16">
            <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        ) : !data?.items.length ? (
          <div className="rounded-xl border border-zinc-200 bg-white p-12 text-center text-zinc-400">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-zinc-300" />
            <p>No alerts found.</p>
          </div>
        ) : (
          data.items.map((alert) => (
            <div
              key={alert.id}
              className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  {/* Risk Badge */}
                  <div className="shrink-0 flex flex-col items-center justify-center w-16 h-16 rounded-xl border-2 border-zinc-100 bg-zinc-50">
                    <span className={`text-2xl font-black leading-none ${RISK_COLOR(alert.risk_score)}`}>
                      {Math.round(alert.risk_score)}
                    </span>
                    <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-400 mt-0.5">Risk</span>
                  </div>

                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${STATUS_STYLES[alert.status] ?? ""}`}>
                        {alert.status.replace("_", " ").toUpperCase()}
                      </span>
                      <span className="text-xs font-semibold text-zinc-700 bg-zinc-100 rounded-full px-2 py-0.5">
                        {ALERT_TYPE_LABELS[alert.alert_type] ?? alert.alert_type}
                      </span>
                    </div>
                    <p className="text-sm text-zinc-600">
                      {(alert.alert_metadata as Record<string, string>)?.detail ?? "Suspicious activity detected."}
                    </p>
                    <p className="text-xs text-zinc-400 mt-1">
                      {new Date(alert.created_at).toLocaleString("en-GB")}
                    </p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {alert.status === "open" && (
                    <button
                      onClick={() => handleStatusChange(alert.id, "under_review")}
                      disabled={updating === alert.id}
                      className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors disabled:opacity-50"
                    >
                      Review
                    </button>
                  )}
                  {alert.status === "under_review" && (
                    <>
                      <button
                        onClick={() => handleStatusChange(alert.id, "escalated")}
                        disabled={updating === alert.id}
                        className="rounded-lg border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700 hover:bg-purple-100 transition-colors disabled:opacity-50"
                      >
                        Escalate
                      </button>
                      <button
                        onClick={() => handleStatusChange(alert.id, "dismissed")}
                        disabled={updating === alert.id}
                        className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs font-semibold text-zinc-600 hover:bg-zinc-100 transition-colors disabled:opacity-50"
                      >
                        Dismiss
                      </button>
                    </>
                  )}
                  {alert.status === "escalated" && (
                    <button
                      onClick={() => handleStatusChange(alert.id, "closed")}
                      disabled={updating === alert.id}
                      className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-50"
                    >
                      Close
                    </button>
                  )}
                  {alert.transaction_id && (
                    <Link
                      href={`/admin/transactions/${alert.transaction_id}`}
                      className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700 hover:bg-teal-100 transition-colors"
                    >
                      View Tx
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-zinc-200 bg-white p-2 text-zinc-400 hover:bg-zinc-50 disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="px-4 text-sm font-medium text-zinc-700">{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-zinc-200 bg-white p-2 text-zinc-400 hover:bg-zinc-50 disabled:opacity-30"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
