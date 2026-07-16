"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone, type FileRejection } from "react-dropzone";
import { toast } from "sonner";
import {
  Upload, FileCheck, FileX, ArrowLeft, ArrowRight,
  Eye, X, RefreshCw, AlertCircle, CheckCircle, Trash2, ShieldCheck,
} from "lucide-react";
import { useCustomer, useDocuments } from "@/hooks/usePortalData";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { uploadDocument, getDocumentOcrData, verifyDocumentOcr, deleteDocument, reprocessDocument } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { cn, formatFileSize, formatDate } from "@/lib/utils";

const DOCUMENT_TYPES = [
  { value: "passport",          label: "Passport",            icon: "🛂", hint: "Main identity document" },
  { value: "national_id",       label: "National ID",         icon: "🪪", hint: "Government-issued ID card" },
  { value: "driving_licence",   label: "Driving Licence",     icon: "🚗", hint: "UK or international licence" },
  { value: "proof_of_address",  label: "Proof of Address",    icon: "🏠", hint: "Utility bill / bank statement (3 months)" },
  { value: "company_document",  label: "Company Document",    icon: "🏢", hint: "Certificate of incorporation" },
] as const;

const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPTED_TYPES = { "image/png": [], "image/jpeg": [], "application/pdf": [] };

type UploadState = {
  file: File;
  progress: number;
  status: "uploading" | "done" | "error";
  docId?: string;
  error?: string;
  preview?: string;
};

type OcrReviewState = {
  documentId: string;
  ocrData: Record<string, any>;
  verificationStatus: string;
  metadata?: Record<string, any>;
};

export default function DocumentsStep() {
  const router = useRouter();
  const { token } = useAuth();
  const { data: customer } = useCustomer();
  const { data: documents, invalidate } = useDocuments(customer?.id);
  const { markStepComplete } = useOnboardingDraft();

  const [selectedType, setSelectedType] = useState<string>("passport");
  const [uploading, setUploading] = useState<UploadState | null>(null);
  const [ocrReview, setOcrReview] = useState<OcrReviewState | null>(null);
  const [viewingOcr, setViewingOcr] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const onDrop = useCallback(
    async (accepted: File[], rejected: FileRejection[]) => {
      if (rejected.length > 0) {
        const msg = rejected[0]?.errors[0]?.message || "File rejected";
        toast.error(msg.includes("size") ? "File exceeds 10 MB limit" : "Only PDF, PNG, JPEG are accepted");
        return;
      }
      if (!accepted[0] || !customer?.id || !token) return;

      const file = accepted[0];
      const preview = file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : undefined;

      setUploading({ file, progress: 0, status: "uploading", preview });

      try {
        const doc = await uploadDocument(
          customer.id,
          selectedType,
          file,
          token,
          (pct) => setUploading((u) => u ? { ...u, progress: pct } : u)
        );
        setUploading((u) => u ? { ...u, status: "done", progress: 100, docId: doc.id } : u);
        await invalidate();
        toast.success(`${file.name} uploaded successfully! Scanning started.`);

        // Auto load the OCR data after upload
        setTimeout(() => {
          setUploading(null);
          loadOcrData(doc.id);
        }, 1500);
      } catch (err) {
        setUploading((u) =>
          u ? { ...u, status: "error", error: err instanceof Error ? err.message : "Upload failed" } : u
        );
        toast.error(err instanceof Error ? err.message : "Upload failed");
      }
    },
    [customer?.id, token, selectedType, invalidate]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE,
    multiple: false,
    disabled: !!uploading,
  });

  const loadOcrData = async (documentId: string) => {
    if (!token) return;
    setActionLoading(true);
    setViewingOcr(documentId);
    try {
      const result = await getDocumentOcrData(documentId, token);
      
      // Flatten the OCR data if it has {value, confidence} structure
      const flattenedData: Record<string, string> = {};
      const ocrData = result.ocr_data as any;
      if (ocrData) {
        Object.entries(ocrData).forEach(([key, val]) => {
          if (val && typeof val === "object" && "value" in val) {
            flattenedData[key] = String((val as any).value || "");
          } else {
            flattenedData[key] = String(val || "");
          }
        });
      }

      setOcrReview({
        documentId,
        ocrData: flattenedData,
        verificationStatus: result.verification_status,
        metadata: result.verification_metadata || {}
      });
    } catch {
      toast.error("OCR scans are processing. Please wait a few seconds and try again.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmOcr = async () => {
    if (!ocrReview || !token) return;
    setActionLoading(true);
    try {
      // Re-map simple form inputs back to the expected payload structure
      const payloadOcr: Record<string, any> = {};
      Object.entries(ocrReview.ocrData).forEach(([k, v]) => {
        payloadOcr[k] = { value: v, confidence: 1.0 };
      });

      const res = await verifyDocumentOcr(ocrReview.documentId, payloadOcr, token);
      toast.success("Document verification completed!");
      setOcrReview(null);
      await invalidate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verification confirmation failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (documentId: string) => {
    if (!token) return;
    if (!confirm("Are you sure you want to delete this document?")) return;
    setActionLoading(true);
    try {
      await deleteDocument(documentId, token);
      toast.success("Document deleted");
      if (ocrReview?.documentId === documentId) {
        setOcrReview(null);
      }
      await invalidate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReprocess = async (documentId: string) => {
    if (!token) return;
    setActionLoading(true);
    try {
      await reprocessDocument(documentId, token);
      toast.success("Reprocessing queued successfully!");
      setOcrReview(null);
      await invalidate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reprocessing request failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleContinue = () => {
    const uploaded = documents?.filter((d) => d.verification_status !== "deleted") ?? [];
    if (uploaded.length === 0) {
      toast.error("Please upload and verify at least one document before continuing");
      return;
    }
    
    // Check if any uploads are still pending verification/OCR review
    const pending = uploaded.some(d => d.verification_status === "pending_confirmation" || d.verification_status === "uploaded");
    if (pending) {
      toast.warning("Please confirm the OCR details of your uploaded documents first");
      return;
    }

    markStepComplete("documents");
    router.push("/customer/onboarding/company");
  };

  const uploadedTypes = new Set(documents?.map((d) => d.document_type) ?? []);

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
          <Upload className="h-5 w-5 text-teal-700" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Secure Document Upload</h1>
          <p className="text-sm text-zinc-500">Step 3 of 5 — Upload and verify identity / corporate verification documents</p>
        </div>
      </div>

      {/* Document Type Selector */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-zinc-700">Select Document Type</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {DOCUMENT_TYPES.map((dt) => {
            const isUploaded = uploadedTypes.has(dt.value);
            return (
              <button
                key={dt.value}
                type="button"
                onClick={() => setSelectedType(dt.value)}
                className={cn(
                  "relative flex flex-col items-center gap-1.5 rounded-lg border-2 p-3 text-center transition-all",
                  selectedType === dt.value
                    ? "border-teal-600 bg-teal-50 shadow-sm"
                    : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50"
                )}
              >
                {isUploaded && (
                  <span className="absolute right-1.5 top-1.5">
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                  </span>
                )}
                <span className="text-xl">{dt.icon}</span>
                <span className="text-xs font-medium text-zinc-800">{dt.label}</span>
                <span className="text-[10px] text-zinc-400">{dt.hint}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Drop Zone */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-zinc-700">
          Upload{" "}
          <span className="text-teal-700">
            {DOCUMENT_TYPES.find((d) => d.value === selectedType)?.label}
          </span>
        </h2>

        {!uploading ? (
          <div
            {...getRootProps()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 transition-all",
              isDragActive
                ? "border-teal-500 bg-teal-50"
                : "border-zinc-200 bg-zinc-50 hover:border-zinc-300 hover:bg-white"
            )}
          >
            <input {...getInputProps()} />
            <div className={cn("flex h-12 w-12 items-center justify-center rounded-full transition-colors", isDragActive ? "bg-teal-100" : "bg-zinc-100")}>
              <Upload className={cn("h-6 w-6 transition-colors", isDragActive ? "text-teal-600" : "text-zinc-400")} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-zinc-700">
                {isDragActive ? "Drop file here" : "Drag & drop or click to browse"}
              </p>
              <p className="mt-1 text-xs text-zinc-400">PDF, PNG, JPEG — up to 10 MB</p>
            </div>
          </div>
        ) : (
          <UploadProgress state={uploading} />
        )}
      </div>

      {/* Uploaded Documents List */}
      {documents && documents.length > 0 && (
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-zinc-700">
            Uploaded Documents ({documents.length})
          </h2>
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-lg border border-zinc-100 bg-zinc-50 p-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white border border-zinc-200">
                    {DOCUMENT_TYPES.find((d) => d.value === doc.document_type)?.icon || "📄"}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-800">{doc.file_name}</p>
                    <p className="text-xs text-zinc-400">
                      {DOCUMENT_TYPES.find((d) => d.value === doc.document_type)?.label}{" "}
                      · {formatFileSize(doc.file_size)} · {formatDate(doc.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2 ml-3">
                  <VerificationBadge status={doc.verification_status} />
                  <button
                    type="button"
                    onClick={() => loadOcrData(doc.id)}
                    className="flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-600 hover:bg-white transition-colors"
                    title="Review Extracted OCR Data"
                  >
                    {actionLoading && viewingOcr === doc.id ? (
                      <RefreshCw className="h-3 w-3 animate-spin" />
                    ) : (
                      <Eye className="h-3 w-3" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(doc.id)}
                    className="rounded-md border border-zinc-200 p-1 text-red-500 hover:bg-white hover:text-red-700 transition-colors"
                    title="Delete Document"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* OCR Preview & Editable Review Form */}
      {ocrReview && (
        <div className="rounded-xl border border-teal-200 bg-teal-50/50 p-5 shadow-sm animate-fade-in space-y-4">
          <div className="flex items-center justify-between border-b border-teal-100 pb-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-teal-700" />
              <h3 className="text-sm font-semibold text-teal-800">Verify OCR Extracted Data</h3>
              <VerificationBadge status={ocrReview.verificationStatus} />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleReprocess(ocrReview.documentId)}
                className="flex items-center gap-1 rounded-md border border-teal-200 px-2.5 py-1 text-[10px] font-medium text-teal-700 hover:bg-teal-100 transition-colors"
              >
                <RefreshCw className="h-3 w-3" /> Force Scan
              </button>
              <button
                onClick={() => setOcrReview(null)}
                className="rounded-md p-1 text-teal-600 hover:bg-teal-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Validation Warnings */}
          {ocrReview.metadata?.validation?.errors?.length > 0 && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-1">
              <p className="text-xs font-bold text-red-800 flex items-center gap-1">
                <AlertCircle className="h-3.5 w-3.5 text-red-600" /> Validation Failures Detected:
              </p>
              <ul className="list-disc pl-5 text-[11px] text-red-700 space-y-0.5">
                {ocrReview.metadata?.validation?.errors?.map((err: string, idx: number) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Verification Results Panel */}
          {ocrReview.metadata?.matching && (
            <div className="grid gap-3 sm:grid-cols-3 bg-white border border-teal-100 rounded-lg p-3 text-center">
              <div>
                <p className="text-[10px] font-semibold text-zinc-400 uppercase">Overall Match Score</p>
                <p className="text-lg font-bold text-teal-700 mt-0.5">
                  {ocrReview.metadata.matching.overall_confidence_score}%
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-zinc-400 uppercase">Name Match</p>
                <p className="text-lg font-bold text-teal-700 mt-0.5">
                  {ocrReview.metadata.matching.name_match_ratio}%
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-zinc-400 uppercase">Risk Evaluation</p>
                <p className={cn(
                  "text-xs font-bold uppercase mt-1 rounded px-1.5 py-0.5 inline-block",
                  ocrReview.metadata.risk?.risk_category === "high" ? "bg-red-50 text-red-700 border border-red-200" :
                  ocrReview.metadata.risk?.risk_category === "medium" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                  "bg-emerald-50 text-emerald-700 border border-emerald-200"
                )}>
                  {ocrReview.metadata.risk?.risk_category || "low"} Risk
                </p>
              </div>
            </div>
          )}

          {/* Editable Inputs for Confirmation */}
          <div className="grid gap-3 sm:grid-cols-2 bg-white rounded-xl border border-teal-100 p-4">
            {Object.keys(ocrReview.ocrData).filter(k => !k.startsWith("_")).map((key) => {
              const val = ocrReview.ocrData[key];
              return (
                <div key={key} className="space-y-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
                    {key.replace(/_/g, " ")}
                  </label>
                  <input
                    type="text"
                    value={val || ""}
                    onChange={(e) => {
                      const nextData = { ...ocrReview.ocrData, [key]: e.target.value };
                      setOcrReview({ ...ocrReview, ocrData: nextData });
                    }}
                    placeholder="—"
                    className="w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-800 focus:border-teal-500 focus:ring-1 focus:ring-teal-100 outline-none"
                  />
                </div>
              );
            })}
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOcrReview(null)}
              className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={actionLoading}
              onClick={handleConfirmOcr}
              className="flex items-center gap-1.5 rounded-lg bg-teal-700 px-5 py-2 text-xs font-bold text-white hover:bg-teal-800 disabled:opacity-60 transition-colors"
            >
              {actionLoading ? (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-b-2 border-white" />
              ) : (
                <>Confirm & Verify Data</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/customer/onboarding/kyc")}
          className="flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <button
          type="button"
          onClick={handleContinue}
          className="flex items-center gap-2 rounded-lg bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 transition-colors"
        >
          Continue <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ─── Sub-Components ───────────────────────────────────────────────────────────
function UploadProgress({ state }: { state: UploadState }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5">
      <div className="flex items-center gap-4">
        {state.preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={state.preview} alt="preview" className="h-16 w-16 rounded-lg object-cover border border-zinc-200" />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-zinc-100">
            <FileCheck className="h-7 w-7 text-zinc-400" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-medium text-zinc-800">{state.file.name}</p>
          <p className="text-xs text-zinc-400">{formatFileSize(state.file.size)}</p>
          {state.status !== "error" ? (
            <div className="mt-2 space-y-1">
              <div className="h-1.5 w-full rounded-full bg-zinc-100">
                <div
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    state.status === "done" ? "bg-emerald-500" : "bg-teal-500"
                  )}
                  style={{ width: `${state.progress}%` }}
                />
              </div>
              <p className="text-xs text-zinc-500">
                {state.status === "done" ? "✓ Upload complete" : `Uploading... ${state.progress}%`}
              </p>
            </div>
          ) : (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-red-600">
              <FileX className="h-3.5 w-3.5" />
              {state.error || "Upload failed"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function VerificationBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const cfg = s.includes("verified") || s.includes("approved")
    ? { cls: "text-emerald-700 bg-emerald-50 border-emerald-200", label: "Verified" }
    : s.includes("rejected") || s.includes("failed") || s.includes("flagged")
    ? { cls: "text-red-700 bg-red-50 border-red-200", label: "Flagged" }
    : s.includes("confirmation")
    ? { cls: "text-blue-700 bg-blue-50 border-blue-200", label: "Pending Confirm" }
    : { cls: "text-amber-700 bg-amber-50 border-amber-200", label: "Processing" };

  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold animate-fade-in", cfg.cls)}>
      {cfg.label}
    </span>
  );
}
