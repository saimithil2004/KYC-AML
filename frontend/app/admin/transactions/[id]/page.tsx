"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getTransaction } from "@/lib/api";
import type { Transaction } from "@/lib/types";
import {
  ArrowLeft, DollarSign, Globe, User, Calendar,
  Hash, CheckCircle, Clock, XCircle,
} from "lucide-react";

const TYPE_COLORS: Record<string, string> = {
  credit: "text-emerald-700 bg-emerald-50 border-emerald-200",
  debit: "text-red-700 bg-red-50 border-red-200",
  transfer: "text-blue-700 bg-blue-50 border-blue-200",
  cash: "text-amber-700 bg-amber-50 border-amber-200",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle className="h-4 w-4 text-emerald-500" />,
  pending: <Clock className="h-4 w-4 text-amber-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
};

export default function TransactionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const router = useRouter();
  const [tx, setTx] = useState<Transaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || !id) return;
    getTransaction(id, token)
      .then(setTx)
      .catch(() => setError("Transaction not found."))
      .finally(() => setLoading(false));
  }, [token, id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
      </div>
    );
  }

  if (error || !tx) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
        <p className="text-red-700 font-semibold">{error || "Transaction not found."}</p>
        <button onClick={() => router.back()} className="mt-4 text-sm text-red-600 underline">Go back</button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Transaction Details</h1>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">{tx.id}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {STATUS_ICONS[tx.status]}
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold capitalize ${tx.status === "completed" ? "text-emerald-700 bg-emerald-50" : tx.status === "failed" ? "text-red-700 bg-red-50" : "text-amber-700 bg-amber-50"}`}>
            {tx.status}
          </span>
        </div>
      </div>

      {/* Amount Hero */}
      <div className="rounded-2xl border border-teal-200 bg-gradient-to-br from-teal-50 to-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-600 mb-1">Transaction Amount</p>
        <p className="text-5xl font-black text-zinc-900">
          {tx.currency} {tx.amount.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <span className={`mt-3 inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold capitalize ${TYPE_COLORS[tx.transaction_type] ?? "text-zinc-600 bg-zinc-50 border-zinc-200"}`}>
          {tx.transaction_type}
        </span>
      </div>

      {/* Detail Cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-zinc-200 bg-white p-6 space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">Receiver Details</h3>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <User className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-zinc-400">Receiver Name</p>
                <p className="text-sm font-semibold text-zinc-900">{tx.receiver_name}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Hash className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-zinc-400">Account Number</p>
                <p className="text-sm font-mono text-zinc-900">{tx.receiver_account_number}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Hash className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-zinc-400">Sort Code</p>
                <p className="text-sm font-mono text-zinc-900">{tx.receiver_sort_code}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Globe className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-zinc-400">Destination Country</p>
                <p className="text-sm font-semibold text-zinc-900">{tx.receiver_country}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-6 space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">Transaction Info</h3>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <DollarSign className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-zinc-400">Currency</p>
                <p className="text-sm font-semibold text-zinc-900">{tx.currency}</p>
              </div>
            </div>
            {tx.reference && (
              <div className="flex items-start gap-3">
                <Hash className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-zinc-400">Reference</p>
                  <p className="text-sm text-zinc-900">{tx.reference}</p>
                </div>
              </div>
            )}
            <div className="flex items-start gap-3">
              <Calendar className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-zinc-400">Created At</p>
                <p className="text-sm text-zinc-900">{new Date(tx.created_at).toLocaleString("en-GB")}</p>
              </div>
            </div>
            {tx.completed_at && (
              <div className="flex items-start gap-3">
                <CheckCircle className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-zinc-400">Completed At</p>
                  <p className="text-sm text-zinc-900">{new Date(tx.completed_at).toLocaleString("en-GB")}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
