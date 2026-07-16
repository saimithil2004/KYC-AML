"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  FileCheck, Shield, AlertCircle, CheckCircle, Clock,
  Eye, RefreshCw, XCircle, Search, User, FileText, Send, Building2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { cn, formatDate, formatFileSize, getStatusColor, getRiskColor } from "@/lib/utils";

type CustomerSummary = {
  id: string;
  first_name?: string;
  last_name?: string;
  customer_type: string;
  status: string;
  created_at: string;
};

type DocumentDetail = {
  id: string;
  document_type: string;
  file_name: string;
  file_path: string;
  content_type?: string;
  file_size?: number;
  verification_status: string;
  ocr_data?: Record<string, any>;
  verification_metadata?: Record<string, any>;
  created_at: string;
};

export default function ComplianceDesk() {
  const { token } = useAuth();
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [selectedKyc, setSelectedKyc] = useState<any | null>(null);
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [officerNotes, setOfficerNotes] = useState("");

  // Load all customers
  useEffect(() => {
    if (!token) return;
    setLoading(true);
    apiRequest<CustomerSummary[]>("/customers/", {}, token)
      .then((data) => setCustomers(data))
      .catch((err) => toast.error("Failed to load customer registry: " + err.message))
      .finally(() => setLoading(false));
  }, [token]);

  // Load selected customer's KYC + documents
  useEffect(() => {
    if (!selectedCustomerId || !token) return;
    setLoading(true);
    setOfficerNotes("");
    
    Promise.allSettled([
      apiRequest<any>(`/kyc/${selectedCustomerId}`, {}, token),
      apiRequest<DocumentDetail[]>(`/documents/customer/${selectedCustomerId}`, {}, token),
    ]).then(([kycRes, docsRes]) => {
      if (kycRes.status === "fulfilled") {
        setSelectedKyc(kycRes.value);
      } else {
        setSelectedKyc(null);
      }
      if (docsRes.status === "fulfilled") {
        setDocuments(docsRes.value);
        if (docsRes.value.length > 0) {
          setSelectedDocId(docsRes.value[0].id);
        } else {
          setSelectedDocId(null);
        }
      } else {
        setDocuments([]);
        setSelectedDocId(null);
      }
    }).finally(() => setLoading(false));
  }, [selectedCustomerId, token]);

  const activeDoc = documents.find((d) => d.id === selectedDocId);

  // Submit compliance decision
  const handleDecision = async (decision: "approved" | "rejected" | "referred") => {
    if (!selectedCustomerId || !token) return;
    setActionLoading(true);
    try {
      await apiRequest(
        `/customers/${selectedCustomerId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            status: decision,
            notes: officerNotes
          })
        },
        token
      );
      
      // Update local state list
      setCustomers((prev) =>
        prev.map((c) => (c.id === selectedCustomerId ? { ...c, status: decision } : c))
      );
      
      toast.success(`Customer status updated to ${decision.toUpperCase()}`);
    } catch (err) {
      toast.error("Decision update failed: " + (err instanceof Error ? err.message : "Error"));
    } finally {
      setActionLoading(false);
    }
  };

  const filteredCustomers = customers.filter((c) => {
    const term = searchQuery.toLowerCase();
    const fullName = `${c.first_name || ""} ${c.last_name || ""}`.toLowerCase();
    return fullName.includes(term) || c.id.toLowerCase().includes(term);
  });

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Overview stats header */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-900">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-zinc-900 font-sans">Verification Desk</h1>
            <p className="text-sm text-zinc-500">Screen OCR extractions, match metrics, and audit fraud scores</p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-12 items-start">
        
        {/* Customer Registry list (left 4 columns) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="rounded-xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-zinc-100 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400 mb-2">Registry</p>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search customer name or ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 bg-white pl-9 pr-4 py-2 text-xs outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-50"
                />
              </div>
            </div>

            <div className="max-h-[500px] overflow-y-auto divide-y divide-zinc-50">
              {filteredCustomers.length === 0 ? (
                <div className="p-8 text-center text-xs text-zinc-400">No customers found</div>
              ) : (
                filteredCustomers.map((c) => {
                  const name = `${c.first_name || ""} ${c.last_name || ""}`.trim() || "Declarant Profile";
                  const active = c.id === selectedCustomerId;
                  return (
                    <button
                      key={c.id}
                      onClick={() => setSelectedCustomerId(c.id)}
                      className={cn(
                        "w-full text-left p-4 hover:bg-zinc-50 transition-colors flex items-center justify-between",
                        active && "bg-teal-50/50 border-l-4 border-teal-600"
                      )}
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-zinc-800 truncate">{name}</p>
                        <p className="text-[10px] text-zinc-400 truncate mt-0.5">{c.id}</p>
                      </div>
                      <span className={cn("rounded-full border px-2 py-0.5 text-[9px] font-bold capitalize", getStatusColor(c.status))}>
                        {c.status.replace(/_/g, " ")}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Selected Customer Verification workspace (right 8 columns) */}
        <div className="lg:col-span-8 space-y-4">
          {!selectedCustomerId ? (
            <div className="rounded-xl border border-zinc-200 border-dashed bg-white p-20 text-center">
              <User className="h-10 w-10 text-zinc-300 mx-auto mb-3" />
              <p className="text-sm font-semibold text-zinc-600">Select a Customer</p>
              <p className="text-xs text-zinc-400 mt-0.5">Pick an applicant from the registry to audit their verification records</p>
            </div>
          ) : (
            <div className="space-y-4">
              
              {/* KYC declaration vs OCR panel */}
              <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
                  <h2 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                    <User className="h-4 w-4 text-zinc-500" /> Declared Profile vs Document Matches
                  </h2>
                  <div className="flex gap-2">
                    {documents.map((d) => (
                      <button
                        key={d.id}
                        onClick={() => setSelectedDocId(d.id)}
                        className={cn(
                          "rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors",
                          selectedDocId === d.id
                            ? "bg-teal-700 text-white border-teal-700"
                            : "bg-white text-zinc-600 hover:bg-zinc-50 border-zinc-200"
                        )}
                      >
                        {d.document_type.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                </div>

                {!activeDoc ? (
                  <p className="text-xs text-zinc-400 text-center py-6">No documents uploaded for this applicant</p>
                ) : (
                  <div className="space-y-4">
                    {/* Document Stats Header */}
                    <div className="grid gap-3 sm:grid-cols-4 bg-zinc-50 border border-zinc-100 rounded-lg p-3 text-center">
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Match Ratio</p>
                        <p className="text-lg font-bold text-teal-700 mt-0.5">
                          {activeDoc.verification_metadata?.matching?.overall_confidence_score ?? "—"}%
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Risk Tier</p>
                        <p className={cn(
                          "text-xs font-bold uppercase mt-1 rounded px-2 py-0.5 inline-block",
                          getRiskColor(activeDoc.verification_metadata?.risk?.risk_category || "")
                        )}>
                          {activeDoc.verification_metadata?.risk?.risk_category ?? "Unknown"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Verification Status</p>
                        <p className={cn("text-xs font-bold uppercase mt-1 rounded px-2 py-0.5 inline-block", getStatusColor(activeDoc.verification_status))}>
                          {activeDoc.verification_status}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">File Type / Size</p>
                        <p className="text-xs font-semibold text-zinc-700 mt-1 capitalize">
                          {activeDoc.content_type?.split("/")[1] || "—"} ({formatFileSize(activeDoc.file_size)})
                        </p>
                      </div>
                    </div>

                    {/* Fraud Detection / Image Quality alerts */}
                    {activeDoc.verification_metadata?.fraud?.fraud_detected && (
                      <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-1.5 flex items-start gap-3">
                        <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-xs font-bold text-red-800">Critical Fraud Indicators Flagged:</p>
                          <ul className="list-disc pl-5 text-[11px] text-red-700 mt-1 space-y-0.5">
                            {activeDoc.verification_metadata.fraud.reasons.map((r: string, idx: number) => (
                              <li key={idx}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}

                    {/* Mismatch & Validation report details */}
                    {activeDoc.verification_metadata?.validation?.errors && activeDoc.verification_metadata.validation.errors.length > 0 && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-1 flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-xs font-bold text-amber-800">Document Validation Failures:</p>
                          <ul className="list-disc pl-5 text-[11px] text-amber-700 mt-1 space-y-0.5">
                            {activeDoc.verification_metadata.validation.errors.map((e: string, idx: number) => (
                              <li key={idx}>{e}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}

                    {/* OCR values comparison */}
                    <div className="rounded-lg border border-zinc-200 overflow-hidden bg-white">
                      <div className="grid grid-cols-3 bg-zinc-50 border-b border-zinc-200 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                        <span>Verification Field</span>
                        <span>Customer Declared</span>
                        <span>Extracted OCR Value</span>
                      </div>
                      <div className="divide-y divide-zinc-100">
                        {[
                          {
                            label: "Full Name",
                            declared: selectedKyc?.full_name || "—",
                            extracted: activeDoc.ocr_data?.full_name?.value || activeDoc.ocr_data?.full_name || "—",
                            match: `${activeDoc.verification_metadata?.matching?.name_match_ratio ?? "—"}% match`
                          },
                          {
                            label: "Date of Birth",
                            declared: selectedKyc?.dob || "—",
                            extracted: activeDoc.ocr_data?.dob?.value || activeDoc.ocr_data?.dob || "—",
                            match: activeDoc.verification_metadata?.matching?.dob_match ? "✓ Matches" : "✕ Discrepancy"
                          },
                          {
                            label: "Address",
                            declared: selectedKyc?.address || "—",
                            extracted: activeDoc.ocr_data?.address?.value || activeDoc.ocr_data?.address || "—",
                            match: `${activeDoc.verification_metadata?.matching?.address_match_ratio ?? "—"}% match`
                          },
                          {
                            label: "Nationality",
                            declared: selectedKyc?.nationality || "—",
                            extracted: activeDoc.ocr_data?.nationality?.value || activeDoc.ocr_data?.nationality || "—",
                            match: activeDoc.verification_metadata?.matching?.nationality_match ? "✓ Matches" : "✕ Discrepancy"
                          },
                        ].map((row) => (
                          <div key={row.label} className="grid grid-cols-3 px-4 py-3 text-xs">
                            <div className="font-semibold text-zinc-800">
                              {row.label}
                              <span className="block text-[9px] text-teal-600 font-normal mt-0.5">{row.match}</span>
                            </div>
                            <div className="text-zinc-600 break-words pr-2">{row.declared}</div>
                            <div className="text-zinc-900 break-words pr-2 font-medium">{row.extracted}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Details and file path */}
                    <div className="text-[11px] text-zinc-400 space-y-0.5">
                      <p>Storage path: <span className="font-mono text-zinc-500 break-all">{activeDoc.file_path}</span></p>
                      <p>OCR engine: <span className="font-medium text-zinc-600">{activeDoc.ocr_data?._ocr_engine_used || "Simulated"}</span></p>
                    </div>

                  </div>
                )}
              </div>

              {/* Compliance decision editor */}
              <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-zinc-800">Compliance Case Notes & Decision</h3>
                
                <textarea
                  value={officerNotes}
                  onChange={(e) => setOfficerNotes(e.target.value)}
                  rows={3}
                  placeholder="Record your compliance evaluation, mismatch rationales, or request details for re-upload..."
                  className="w-full rounded-lg border border-zinc-300 p-3 text-xs outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-50"
                />

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDecision("approved")}
                      disabled={actionLoading}
                      className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-60 transition-colors"
                    >
                      <CheckCircle className="h-4 w-4" /> Approve Applicant
                    </button>
                    <button
                      onClick={() => handleDecision("rejected")}
                      disabled={actionLoading}
                      className="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-red-700 disabled:opacity-60 transition-colors"
                    >
                      <XCircle className="h-4 w-4" /> Reject Applicant
                    </button>
                    <button
                      onClick={() => handleDecision("referred")}
                      disabled={actionLoading}
                      className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-amber-700 disabled:opacity-60 transition-colors"
                    >
                      <AlertCircle className="h-4 w-4" /> Escalated Review
                    </button>
                  </div>

                  <p className="text-[10px] text-zinc-400">Officer decisions update status in the customer portal immediately</p>
                </div>
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}

// ─── AlertTriangle local icon fallback ───────────────────────────────────────
function AlertTriangle({ className }: { className?: string }) {
  return <AlertCircle className={className} />;
}
