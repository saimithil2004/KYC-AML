"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Briefcase, Search, Filter, ShieldAlert, CheckCircle, Clock,
  ArrowRight, RefreshCw, FileText, UserPlus, Users, Activity
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { listInvestigations, getInvestigationDashboard } from "@/lib/api";
import { Investigation, InvestigationDashboardMetrics } from "@/lib/types";

export default function InvestigationsDashboard() {
  const { user } = useAuth();
  const token = localStorage.getItem("token") || "";

  const [metrics, setMetrics] = useState<InvestigationDashboardMetrics | null>(null);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  
  // Search & Filter
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  const [loading, setLoading] = useState(false);
  const [errMessage, setErrMessage] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setErrMessage("");
    try {
      // 1. Get dashboard workload metrics
      const m = await getInvestigationDashboard(token);
      setMetrics(m);

      // 2. List investigations with page, status, risk_level
      const res = await listInvestigations(token, {
        page,
        page_size: 10,
        status: statusFilter || undefined,
        risk_level: riskFilter || undefined
      });
      setInvestigations(res.items);
      setTotalItems(res.total);
    } catch (err: any) {
      console.error(err);
      setErrMessage("Failed to load investigation workspace statistics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, statusFilter, riskFilter]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Investigations Dashboard</h1>
          <p className="text-sm text-zinc-500">
            Monitor workloads, evaluate SAR drafts, and manage case escalations.
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

      {errMessage && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-100 text-rose-800 text-sm font-medium">
          {errMessage}
        </div>
      )}

      {/* Grid of Workload KPI Cards (Part 13) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Open Cases</span>
            <Briefcase className="h-5 w-5 text-indigo-500" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{metrics?.open_investigations ?? 0}</p>
          <p className="text-xs text-zinc-500">active reviews</p>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Pending SARs</span>
            <Clock className="h-5 w-5 text-amber-500" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{metrics?.pending_sar ?? 0}</p>
          <p className="text-xs text-zinc-500">in draft state</p>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">SARs Submitted</span>
            <CheckCircle className="h-5 w-5 text-teal-500" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{metrics?.sar_submitted ?? 0}</p>
          <p className="text-xs text-zinc-500">filed reports</p>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Evidence Files</span>
            <FileText className="h-5 w-5 text-indigo-500" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{metrics?.evidence_uploaded ?? 0}</p>
          <p className="text-xs text-zinc-500">documents stored</p>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Avg Resolution Time</span>
            <Activity className="h-5 w-5 text-teal-600" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{metrics?.average_investigation_time_hours ?? 0} hrs</p>
          <p className="text-xs text-zinc-500">hours per case</p>
        </div>
      </div>

      {/* Main Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Active Investigations Table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-zinc-900 text-sm">Active Investigations Workspace</h3>
              {/* Filters */}
              <div className="flex items-center gap-2">
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                  className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs focus:outline-none focus:border-teal-500 text-zinc-700"
                >
                  <option value="">All Statuses</option>
                  <option value="open">Open</option>
                  <option value="under_review">Under Review</option>
                  <option value="edd_required">EDD Required</option>
                  <option value="escalated">Escalated</option>
                  <option value="closed">Closed</option>
                </select>

                <select
                  value={riskFilter}
                  onChange={(e) => { setRiskFilter(e.target.value); setPage(1); }}
                  className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs focus:outline-none focus:border-teal-500 text-zinc-700"
                >
                  <option value="">All Risks</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-zinc-50 border-b border-zinc-200 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                    <th className="p-3">Case ID</th>
                    <th className="p-3">Risk Level</th>
                    <th className="p-3">Assigned Investigator</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Created</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-150 text-xs text-zinc-700">
                  {investigations.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-zinc-400">
                        No investigations match the selected filters.
                      </td>
                    </tr>
                  ) : (
                    investigations.map((i) => (
                      <tr key={i.id} className="hover:bg-zinc-50/50">
                        <td className="p-3 font-mono">{i.case_id.slice(0, 8)}...</td>
                        <td className="p-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            i.risk_level === "critical"
                              ? "bg-rose-100 text-rose-700 border border-rose-200"
                              : i.risk_level === "high"
                              ? "bg-rose-50 text-rose-600 border border-rose-150"
                              : i.risk_level === "medium"
                              ? "bg-amber-50 text-amber-700 border border-amber-150"
                              : "bg-teal-50 text-teal-700"
                          }`}>
                            {i.risk_level}
                          </span>
                        </td>
                        <td className="p-3 text-zinc-500 font-medium">
                          {i.assigned_to ? "Assigned" : "Unassigned"}
                        </td>
                        <td className="p-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                            i.status === "closed"
                              ? "bg-zinc-100 text-zinc-600"
                              : i.status === "escalated"
                              ? "bg-rose-50 text-rose-600"
                              : i.status === "edd_required"
                              ? "bg-amber-50 text-amber-700"
                              : "bg-teal-50 text-teal-700 border border-teal-100"
                          }`}>
                            {i.status.replace("_", " ")}
                          </span>
                        </td>
                        <td className="p-3 text-zinc-500">
                          {new Date(i.created_at).toLocaleDateString()}
                        </td>
                        <td className="p-3 text-right">
                          <Link
                            href={`/admin/investigations/${i.id}`}
                            className="inline-flex items-center gap-1 rounded bg-teal-600 hover:bg-teal-700 px-2.5 py-1 text-[11px] font-bold text-white shadow-sm transition"
                          >
                            Investigate <ArrowRight className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalItems > 10 && (
              <div className="flex justify-between items-center text-xs text-zinc-500 border-t border-zinc-150 pt-3">
                <span>Page {page} of {Math.ceil(totalItems / 10)}</span>
                <div className="flex gap-2">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                    className="px-2.5 py-1 border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page * 10 >= totalItems}
                    onClick={() => setPage(page + 1)}
                    className="px-2.5 py-1 border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Column: Investigator Workload & Workload Balancing */}
        <div className="space-y-6">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
            <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-2">
              <Users className="h-4 w-4 text-zinc-500" />
              Workload Balancing
            </h3>
            <p className="text-xs text-zinc-500">Current active cases assigned across compliance investigators.</p>
            
            <div className="space-y-3.5">
              {metrics?.investigator_workload.map((inv) => (
                <div key={inv.user_id} className="space-y-1.5 border-b border-zinc-100 pb-3 last:border-0 last:pb-0">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-zinc-800 truncate max-w-[170px]">{inv.email}</span>
                    <span className="text-zinc-500">{inv.active_cases} active cases</span>
                  </div>
                  {/* Progress bar mock */}
                  <div className="h-2 w-full bg-zinc-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        inv.active_cases >= 8
                          ? "bg-rose-500"
                          : inv.active_cases >= 4
                          ? "bg-amber-500"
                          : "bg-teal-500"
                      }`}
                      style={{ width: `${Math.min((inv.active_cases / 10) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
              {(!metrics?.investigator_workload || metrics.investigator_workload.length === 0) && (
                <p className="text-xs text-zinc-400 text-center py-4">No investigators logged.</p>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
