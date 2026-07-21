"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { listAuditLogs } from "@/lib/api";
import type { AuditLog, Paginated } from "@/lib/types";
import { ScrollText, RefreshCw, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from "lucide-react";

const PAGE_SIZE = 30;

const ACTION_COLORS: Record<string, string> = {
  CREATE: "text-emerald-700 bg-emerald-50",
  UPDATE: "text-blue-700 bg-blue-50",
  DELETE: "text-red-700 bg-red-50",
  CASE_DECISION: "text-purple-700 bg-purple-50",
  INITIATE: "text-teal-700 bg-teal-50",
  CSV: "text-amber-700 bg-amber-50",
  RESCREENING: "text-teal-700 bg-teal-50",
};

function getActionColor(action: string): string {
  const prefix = action.split("_")[0];
  return ACTION_COLORS[prefix] ?? "text-zinc-600 bg-zinc-100";
}

export default function AuditLogPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Paginated<AuditLog> | null>(null);
  const [page, setPage] = useState(1);
  const [filterEntity, setFilterEntity] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listAuditLogs(token, {
        page,
        entity_name: filterEntity || undefined,
        action: filterAction || undefined,
      });
      setData(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, page, filterEntity, filterAction]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Audit Log</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Immutable record of all compliance operations</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={filterEntity}
          onChange={(e) => { setFilterEntity(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Entities</option>
          <option value="transaction">Transaction</option>
          <option value="alert">Alert</option>
          <option value="case">Case</option>
          <option value="customer">Customer</option>
          <option value="document">Document</option>
        </select>
        <input
          type="text"
          placeholder="Filter by action…"
          value={filterAction}
          onChange={(e) => { setFilterAction(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 placeholder:text-zinc-400 focus:border-teal-500 focus:outline-none"
        />
        <p className="ml-auto text-sm text-zinc-500">{data ? `${data.total} entries` : ""}</p>
      </div>

      {/* Log Entries */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden shadow-sm">
        {loading ? (
          <div className="flex justify-center py-16">
            <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        ) : !data?.items.length ? (
          <div className="flex flex-col items-center py-16 text-zinc-400">
            <ScrollText className="h-8 w-8 mb-2 text-zinc-300" />
            <p className="text-sm">No audit log entries found.</p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-zinc-100">
            <thead className="bg-zinc-50">
              <tr>
                {["Timestamp", "Action", "Entity", "Entity ID", "User", "IP", "Details"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {data.items.map((log) => (
                <>
                  <tr key={log.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-zinc-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString("en-GB")}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold uppercase ${getActionColor(log.action)}`}>
                        {log.action.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs font-medium text-zinc-700 capitalize">{log.entity_name}</td>
                    <td className="px-4 py-3 text-xs font-mono text-zinc-500">{log.entity_id.slice(0, 8)}…</td>
                    <td className="px-4 py-3 text-xs font-mono text-zinc-500">
                      {log.user_id ? log.user_id.slice(0, 8) + "…" : "system"}
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-400">{log.ip_address ?? "—"}</td>
                    <td className="px-4 py-3">
                      {(log.old_values || log.new_values) && (
                        <button
                          onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                          className="text-xs text-teal-600 hover:text-teal-800 flex items-center gap-1"
                        >
                          {expanded === log.id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                          {expanded === log.id ? "Hide" : "Show"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expanded === log.id && (
                    <tr key={`${log.id}-detail`} className="bg-zinc-50">
                      <td colSpan={7} className="px-6 py-4">
                        <div className="grid grid-cols-2 gap-4">
                          {log.old_values && (
                            <div>
                              <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Before</p>
                              <pre className="text-xs text-zinc-700 bg-white border border-zinc-200 rounded p-2 overflow-auto">
                                {JSON.stringify(log.old_values, null, 2)}
                              </pre>
                            </div>
                          )}
                          {log.new_values && (
                            <div>
                              <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">After</p>
                              <pre className="text-xs text-zinc-700 bg-white border border-zinc-200 rounded p-2 overflow-auto">
                                {JSON.stringify(log.new_values, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}

        {data && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
            <p className="text-sm text-zinc-500">{(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total}</p>
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
