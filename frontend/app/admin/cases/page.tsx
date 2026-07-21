"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { listCases } from "@/lib/api";
import type { Case, Paginated } from "@/lib/types";
import {
  Briefcase, RefreshCw, ChevronLeft, ChevronRight,
  AlertTriangle, Clock, CheckCircle, Eye, Filter,
} from "lucide-react";
import Link from "next/link";

const PAGE_SIZE = 20;

const PRIORITY_STYLES: Record<string, string> = {
  critical: "text-red-700 bg-red-50 border-red-300",
  high: "text-orange-700 bg-orange-50 border-orange-300",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low: "text-emerald-700 bg-emerald-50 border-emerald-200",
};

const STATUS_STYLES: Record<string, string> = {
  open: "text-red-700 bg-red-50",
  investigating: "text-blue-700 bg-blue-50",
  under_review: "text-amber-700 bg-amber-50",
  waiting_info: "text-purple-700 bg-purple-50",
  approved: "text-emerald-700 bg-emerald-50",
  rejected: "text-zinc-700 bg-zinc-100",
  closed: "text-zinc-600 bg-zinc-100",
  escalated: "text-purple-700 bg-purple-50",
};

const PRIORITY_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };

export default function CasesPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Paginated<Case> | null>(null);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listCases(token, {
        page,
        page_size: PAGE_SIZE,
        status: filterStatus || undefined,
        priority: filterPriority || undefined,
        sort_dir: "desc",
      });
      setData(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, page, filterStatus, filterPriority]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  const statCounts = data?.items.reduce((acc, c) => {
    acc[c.priority] = (acc[c.priority] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>) ?? {};

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Case Management</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Investigation cases for AML review and compliance decisions</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Priority Stats */}
      <div className="grid grid-cols-4 gap-4">
        {(["critical", "high", "medium", "low"] as const).map((priority) => (
          <div
            key={priority}
            onClick={() => { setFilterPriority(filterPriority === priority ? "" : priority); setPage(1); }}
            className={`cursor-pointer rounded-xl border-2 p-4 transition-all ${filterPriority === priority ? PRIORITY_STYLES[priority] : "border-zinc-200 bg-white"}`}
          >
            <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">{priority}</p>
            <p className="text-3xl font-black text-zinc-900 mt-1">{statCounts[priority] ?? 0}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={filterPriority}
          onChange={(e) => { setFilterPriority(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="investigating">Investigating</option>
          <option value="under_review">Under Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="closed">Closed</option>
        </select>
        <div className="ml-auto text-sm text-zinc-500">
          {data ? `${data.total} total case${data.total !== 1 ? "s" : ""}` : ""}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden shadow-sm">
        <table className="min-w-full divide-y divide-zinc-100">
          <thead className="bg-zinc-50">
            <tr>
              {["Case ID", "Customer", "Priority", "Status", "SAR Filed", "Created", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-zinc-500">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="py-16 text-center">
                  <RefreshCw className="h-5 w-5 animate-spin mx-auto text-zinc-400" />
                </td>
              </tr>
            ) : !data?.items.length ? (
              <tr>
                <td colSpan={7} className="py-16 text-center text-sm text-zinc-400">
                  <Briefcase className="h-8 w-8 mx-auto mb-2 text-zinc-300" />
                  No cases found.
                </td>
              </tr>
            ) : (
              data.items.map((c) => (
                <tr key={c.id} className="hover:bg-zinc-50 transition-colors">
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-zinc-500">{c.id.slice(0, 8)}…</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-zinc-600">{c.customer_id.slice(0, 8)}…</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold uppercase ${PRIORITY_STYLES[c.priority] ?? ""}`}>
                      {c.priority}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLES[c.status] ?? ""}`}>
                      {c.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {c.sar_filed ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-700">
                        <CheckCircle className="h-3.5 w-3.5" /> Filed
                      </span>
                    ) : (
                      <span className="text-xs text-zinc-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-500">
                    {new Date(c.created_at).toLocaleDateString("en-GB")}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/cases/${c.id}`}
                      className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-800 transition-colors"
                    >
                      <Eye className="h-3.5 w-3.5" /> Investigate
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {data && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
            <p className="text-sm text-zinc-500">
              {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="rounded p-1 text-zinc-400 hover:bg-zinc-100 disabled:opacity-30">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-3 text-sm font-medium text-zinc-700">{page} / {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="rounded p-1 text-zinc-400 hover:bg-zinc-100 disabled:opacity-30">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
