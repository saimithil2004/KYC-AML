"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  listTransactions, importTransactionsCsv,
} from "@/lib/api";
import type { Transaction, Paginated } from "@/lib/types";
import {
  ArrowUpDown, Search, Upload, Download, RefreshCw,
  TrendingUp, TrendingDown, AlertCircle, CheckCircle,
  Filter, ChevronLeft, ChevronRight, Eye,
} from "lucide-react";
import Link from "next/link";

const PAGE_SIZE = 20;

const TYPE_COLORS: Record<string, string> = {
  credit: "text-emerald-700 bg-emerald-50 border-emerald-200",
  debit: "text-red-700 bg-red-50 border-red-200",
  transfer: "text-blue-700 bg-blue-50 border-blue-200",
  cash: "text-amber-700 bg-amber-50 border-amber-200",
};

const STATUS_COLORS: Record<string, string> = {
  completed: "text-emerald-700 bg-emerald-50",
  pending: "text-amber-700 bg-amber-50",
  failed: "text-red-700 bg-red-50",
  cancelled: "text-zinc-600 bg-zinc-100",
};

export default function TransactionsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Paginated<Transaction> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ message: string; imported: number; alerts_generated: number } | null>(null);
  const [importError, setImportError] = useState("");

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listTransactions(token, {
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        status: filterStatus || undefined,
        transaction_type: filterType || undefined,
        sort_dir: "desc",
      });
      setData(result);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, page, search, filterStatus, filterType]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setImporting(true);
    setImportResult(null);
    setImportError("");
    try {
      const result = await importTransactionsCsv(file, token);
      setImportResult(result);
      fetchData();
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const stats = data ? {
    total: data.total,
    completed: data.items.filter(t => t.status === "completed").length,
    avgAmount: data.items.length ? data.items.reduce((s, t) => s + t.amount, 0) / data.items.length : 0,
  } : null;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Transaction Monitor</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Manage, import, and screen all customer transactions</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <label className="flex items-center gap-1.5 cursor-pointer rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 transition-colors">
            <Upload className="h-4 w-4" />
            {importing ? "Importing…" : "Import CSV"}
            <input type="file" accept=".csv" className="hidden" onChange={handleCsvImport} disabled={importing} />
          </label>
        </div>
      </div>

      {/* Import Result Banner */}
      {importResult && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 flex items-start gap-3">
          <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-emerald-800">{importResult.message}</p>
            <p className="text-sm text-emerald-700 mt-0.5">
              {importResult.imported} imported · {importResult.alerts_generated} alert(s) generated
            </p>
          </div>
        </div>
      )}
      {importError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
          <p className="text-sm text-red-800">{importError}</p>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Total Transactions", value: stats.total.toLocaleString(), icon: ArrowUpDown, color: "text-teal-600" },
            { label: "Completed", value: stats.completed.toLocaleString(), icon: CheckCircle, color: "text-emerald-600" },
            { label: "Avg Amount", value: `£${stats.avgAmount.toFixed(2)}`, icon: TrendingUp, color: "text-blue-600" },
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
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
          <input
            type="text"
            placeholder="Search receiver, reference…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full rounded-lg border border-zinc-200 bg-white pl-9 pr-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Types</option>
          <option value="credit">Credit</option>
          <option value="debit">Debit</option>
          <option value="transfer">Transfer</option>
          <option value="cash">Cash</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-100">
            <thead className="bg-zinc-50">
              <tr>
                {["Date", "Receiver", "Country", "Amount", "Type", "Status", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-sm text-zinc-400">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
                    Loading transactions…
                  </td>
                </tr>
              ) : !data?.items.length ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-sm text-zinc-400">
                    No transactions found.
                  </td>
                </tr>
              ) : (
                data.items.map((tx) => (
                  <tr key={tx.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3 text-sm text-zinc-600 whitespace-nowrap">
                      {new Date(tx.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-zinc-900">{tx.receiver_name}</div>
                      <div className="text-xs text-zinc-500">{tx.receiver_account_number}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-600">{tx.receiver_country}</td>
                    <td className="px-4 py-3">
                      <span className="text-sm font-bold text-zinc-900">
                        {tx.currency} {tx.amount.toLocaleString("en-GB", { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${TYPE_COLORS[tx.transaction_type] ?? "text-zinc-700 bg-zinc-50 border-zinc-200"}`}>
                        {tx.transaction_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${STATUS_COLORS[tx.status] ?? "text-zinc-700 bg-zinc-100"}`}>
                        {tx.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/admin/transactions/${tx.id}`}
                        className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-800 transition-colors"
                      >
                        <Eye className="h-3.5 w-3.5" /> View
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
            <p className="text-sm text-zinc-500">
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded p-1 text-zinc-400 hover:bg-zinc-100 disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-3 text-sm font-medium text-zinc-700">{page} / {totalPages}</span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded p-1 text-zinc-400 hover:bg-zinc-100 disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* CSV Template Download */}
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-zinc-700">CSV Import Template</p>
          <p className="text-xs text-zinc-500 mt-0.5">
            Required columns: sender_account_number, sender_sort_code, receiver_account_number, receiver_sort_code, receiver_name, receiver_country, amount, currency, transaction_type
          </p>
        </div>
        <button
          onClick={() => {
            const csv = "sender_account_number,sender_sort_code,receiver_account_number,receiver_sort_code,receiver_name,receiver_country,amount,currency,transaction_type,reference\n12345678,20-00-00,87654321,30-00-00,John Doe,United Kingdom,500.00,GBP,transfer,Payment";
            const blob = new Blob([csv], { type: "text/csv" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = "transactions_template.csv"; a.click();
          }}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 transition-colors"
        >
          <Download className="h-3.5 w-3.5" /> Download Template
        </button>
      </div>
    </div>
  );
}
