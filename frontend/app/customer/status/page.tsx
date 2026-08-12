"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity, CheckCircle, Clock, AlertTriangle, XCircle, RefreshCw,
  Shield, FileSearch, User, Globe, BarChart3, Eye, FileCheck,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useCustomer, useKycProfile, useDocuments } from "@/hooks/usePortalData";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import type { RiskScore, Case, DocumentRecord } from "@/lib/types";
import { cn, formatDate, getRiskColor, getStatusColor } from "@/lib/utils";

type TimelineStage = {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  status: "completed" | "in_progress" | "pending" | "failed" | "skipped";
  completedAt?: string;
  detail?: string;
};

function buildTimeline(
  customer: { status: string; created_at: string } | null,
  kyc: { risk_category?: string; nationality?: string } | null,
  documents: DocumentRecord[] | null,
  riskScore: RiskScore | null,
  caseData: Case | null
): TimelineStage[] {
  const s = customer?.status?.toLowerCase() ?? "";

  const submitted = !["onboarding"].includes(s);
  const kycDone = !["onboarding", "pending_verification"].includes(s) || kyc != null;
  const docsDone = (documents && documents.length > 0) || kycDone;
  const amlDone = riskScore != null;
  const riskDone = amlDone;
  const isReferred = s === "referred" || caseData?.status === "open";
  const isApproved = s === "approved";
  const isRejected = s === "rejected";
  const manualNeeded = isReferred;
  const completed = isApproved || isRejected;

  const docCount = documents?.length ?? 0;
  const pepPts = riskScore?.breakdown?.pep ?? 0;
  const sanctionsPts = riskScore?.breakdown?.sanctions ?? 0;
  const countryPts = riskScore?.breakdown?.country ?? 0;

  return [
    {
      id: "submitted",
      label: "Application Submitted",
      description: "KYC form and supporting documents received",
      icon: FileCheck,
      status: submitted ? "completed" : "in_progress",
      detail: submitted
        ? `Application confirmed on ${customer ? formatDate(customer.created_at) : "file"}`
        : "Awaiting final application submission",
    },
    {
      id: "kyc_check",
      label: "KYC Verification",
      description: "Identity and declaration cross-checking",
      icon: User,
      status: kycDone ? "completed" : submitted ? "in_progress" : "pending",
      detail: kyc
        ? `Profile validated — Risk category: ${(kyc.risk_category || "low").toUpperCase()} (${kyc.nationality || "UK"})`
        : "Verifying identity declarations",
    },
    {
      id: "doc_check",
      label: "Document Verification",
      description: "OCR extraction and document authenticity checks",
      icon: FileSearch,
      status: docsDone ? "completed" : kycDone ? "in_progress" : "pending",
      detail: docCount > 0
        ? `${docCount} document(s) uploaded and OCR verified`
        : "Extracting and validating document data",
    },
    {
      id: "aml_screening",
      label: "AML Screening",
      description: "PEP, Sanctions, Country Risk, and Source of Funds screening",
      icon: Shield,
      status: amlDone ? "completed" : docsDone ? "in_progress" : "pending",
      detail: amlDone
        ? `Screening complete — Sanctions: ${sanctionsPts > 0 ? `${sanctionsPts} pts` : "clean"}, PEP: ${pepPts > 0 ? `${pepPts} pts` : "clean"}`
        : "Running AI-powered AML agent pipeline",
    },
    {
      id: "risk_analysis",
      label: "Risk Analysis",
      description: "Aggregate risk scoring across all dimensions",
      icon: BarChart3,
      status: riskDone ? "completed" : amlDone ? "in_progress" : "pending",
      detail: riskScore
        ? `Score: ${riskScore.overall_score.toFixed(1)} / 100 — Tier: ${riskScore.risk_tier.toUpperCase()}`
        : "Calculating composite risk score",
    },
    {
      id: "manual_review",
      label: "Manual Review",
      description: "Compliance officer investigation (if required)",
      icon: Eye,
      status: manualNeeded ? "in_progress" : completed ? "skipped" : "pending",
      detail: manualNeeded
        ? `Case #${caseData ? caseData.id.slice(0, 8) : "REVIEW"} escalated to compliance officer for manual review`
        : completed
        ? "Auto-resolved — no manual review required"
        : "Pending risk analysis outcome",
    },
    {
      id: "country_check",
      label: "Geopolitical Screening",
      description: "FATF watchlist and high-risk jurisdiction checks",
      icon: Globe,
      status: amlDone ? (countryPts > 0 ? "failed" : "completed") : "pending",
      detail: riskScore
        ? `Country risk score: ${countryPts} pts ${countryPts > 0 ? "(High Risk Jurisdiction)" : "(Clean)"}`
        : "Pending",
    },
    {
      id: "completed",
      label: "Decision",
      description: "Final compliance decision",
      icon: CheckCircle,
      status: isApproved ? "completed" : isRejected ? "failed" : "pending",
      detail: isApproved
        ? "Application approved — onboarding complete"
        : isRejected
        ? "Application declined — contact compliance team"
        : "Awaiting completion of all checks",
    },
  ];
}

export default function StatusPage() {
  const { token } = useAuth();
  const { data: customer, isLoading: custLoading, refetch } = useCustomer();
  const { data: kyc } = useKycProfile(customer?.id);
  const { data: documents } = useDocuments(customer?.id);
  const [riskScore, setRiskScore] = useState<RiskScore | null>(null);
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!customer?.id || !token) return;
    const loadData = async () => {
      setLoading(true);
      try {
        const [scores, cases] = await Promise.allSettled([
          apiRequest<RiskScore[]>(`/risk-scores/customer/${customer.id}`, {}, token),
          apiRequest<Case[]>(`/cases/customer/${customer.id}`, {}, token),
        ]);
        if (scores.status === "fulfilled" && scores.value.length > 0) {
          setRiskScore(scores.value[0]);
        }
        if (cases.status === "fulfilled" && cases.value.length > 0) {
          setCaseData(cases.value[0]);
        }
      } catch {
        // silently handle — endpoints may not yet exist
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [customer?.id, token]);

  const timeline = customer
    ? buildTimeline(customer, kyc ?? null, documents ?? null, riskScore, caseData)
    : [];

  const overallStatus = customer?.status ?? "loading";

  return (
    <ProtectedRoute>
      <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
        {/* Header */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
                <Activity className="h-5 w-5 text-teal-700" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-zinc-900">Application Status</h1>
                <p className="text-sm text-zinc-500">Real-time AML workflow tracking</p>
              </div>
            </div>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
              Refresh
            </button>
          </div>
        </div>

        {/* Status Summary */}
        {customer && (
          <div className="grid gap-3 sm:grid-cols-3">
            <div className={cn("rounded-xl border p-4", getStatusColor(overallStatus))}>
              <p className="text-[10px] font-semibold uppercase tracking-wide opacity-70">Application Status</p>
              <p className="mt-1 text-lg font-bold capitalize">{overallStatus.replace(/_/g, " ")}</p>
            </div>
            {riskScore && (
              <div className={cn("rounded-xl border p-4", getRiskColor(riskScore.risk_tier))}>
                <p className="text-[10px] font-semibold uppercase tracking-wide opacity-70">Risk Tier</p>
                <p className="mt-1 text-lg font-bold capitalize">{riskScore.risk_tier}</p>
                <p className="text-xs opacity-70">Score: {riskScore.overall_score.toFixed(1)} / 100</p>
              </div>
            )}
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Last Updated</p>
              <p className="mt-1 text-sm font-semibold text-zinc-800">{formatDate(customer.created_at)}</p>
              <p className="text-xs text-zinc-400">Customer since</p>
            </div>
          </div>
        )}

        {/* Risk Score Breakdown */}
        {riskScore && (
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold text-zinc-800">Risk Score Breakdown</h2>
            <div className="space-y-3">
              {Object.entries(riskScore.breakdown).map(([key, score]) => {
                const maxScores: Record<string, number> = {
                  pep: 25,
                  sanctions: 35,
                  country: 20,
                  document: 20,
                  transaction: 20,
                };
                const max = maxScores[key] ?? 20;
                const pct = (score / max) * 100;
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium capitalize text-zinc-600">
                        {key.replace(/_/g, " ")}
                      </span>
                      <span className={cn("text-xs font-bold", score > 0 ? "text-red-600" : "text-emerald-600")}>
                        {score} / {max} pts
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-zinc-100">
                      <div
                        className={cn(
                          "h-2 rounded-full transition-all duration-700",
                          score > max * 0.6 ? "bg-red-500" : score > 0 ? "bg-amber-400" : "bg-emerald-400"
                        )}
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* AML Workflow Timeline */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="mb-5 text-sm font-semibold text-zinc-800">AML Workflow Timeline</h2>
          <div className="relative space-y-1">
            {timeline.map((stage, i) => {
              const Icon = stage.icon;
              const isLast = i === timeline.length - 1;
              return (
                <div key={stage.id} className="relative flex gap-4">
                  {/* Connector line */}
                  {!isLast && (
                    <div
                      className={cn(
                        "absolute left-[15px] top-9 h-full w-0.5",
                        stage.status === "completed" ? "bg-teal-300" : "bg-zinc-200"
                      )}
                    />
                  )}

                  {/* Icon */}
                  <div
                    className={cn(
                      "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-all",
                      stage.status === "completed"
                        ? "border-teal-500 bg-teal-500 text-white"
                        : stage.status === "in_progress"
                        ? "border-teal-400 bg-teal-50 text-teal-600 animate-pulse-glow"
                        : stage.status === "failed"
                        ? "border-red-400 bg-red-50 text-red-600"
                        : stage.status === "skipped"
                        ? "border-zinc-200 bg-zinc-50 text-zinc-300"
                        : "border-zinc-200 bg-white text-zinc-300"
                    )}
                  >
                    {stage.status === "completed" ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : stage.status === "failed" ? (
                      <XCircle className="h-4 w-4" />
                    ) : stage.status === "in_progress" ? (
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    ) : stage.status === "skipped" ? (
                      <Icon className="h-3.5 w-3.5" />
                    ) : (
                      <Clock className="h-3.5 w-3.5" />
                    )}
                  </div>

                  {/* Content */}
                  <div className={cn("flex-1 pb-6", isLast && "pb-0")}>
                    <div className="flex items-center gap-2">
                      <p
                        className={cn(
                          "text-sm font-semibold",
                          stage.status === "completed" ? "text-zinc-800" :
                          stage.status === "in_progress" ? "text-teal-700" :
                          stage.status === "failed" ? "text-red-700" :
                          "text-zinc-400"
                        )}
                      >
                        {stage.label}
                      </p>
                      {stage.status === "in_progress" && (
                        <span className="rounded-full bg-teal-100 px-2 py-0.5 text-[10px] font-semibold text-teal-700">
                          In Progress
                        </span>
                      )}
                      {stage.status === "failed" && (
                        <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">
                          Flagged
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-zinc-500">{stage.description}</p>
                    {stage.detail && (
                      <p className={cn(
                        "mt-1 text-xs",
                        stage.status === "completed" ? "text-teal-700" :
                        stage.status === "failed" ? "text-red-600" :
                        "text-zinc-400"
                      )}>
                        {stage.detail}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Alert if referred */}
        {customer?.status === "referred" && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-800">Manual Review Required</p>
              <p className="text-xs text-amber-700 mt-1">
                Your application has been flagged for manual review by our compliance team. This typically takes 1–3 business days. You will be contacted by email with any additional requirements.
              </p>
            </div>
          </div>
        )}

        {/* Approved */}
        {customer?.status === "approved" && (
          <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <CheckCircle className="h-5 w-5 shrink-0 text-emerald-600 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-emerald-800">Application Approved</p>
              <p className="text-xs text-emerald-700 mt-1">
                Your KYC verification is complete. Welcome aboard. Your account is now fully active.
              </p>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <Link
            href="/customer/dashboard"
            className="flex-1 rounded-lg border border-zinc-300 py-2.5 text-center text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
          >
            Back to Dashboard
          </Link>
          {customer?.status !== "approved" && (
            <Link
              href="/customer/onboarding/review"
              className="flex-1 rounded-lg bg-teal-700 py-2.5 text-center text-sm font-semibold text-white hover:bg-teal-800 transition-colors"
            >
              Update Application
            </Link>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
