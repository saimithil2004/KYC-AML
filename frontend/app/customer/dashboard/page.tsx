"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Gauge, UserRound, FileText, Upload, Building2, ClipboardCheck,
  Activity, CheckCircle, Circle, Clock, AlertTriangle, ArrowRight,
  TrendingUp, Shield, FileCheck, Zap,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useCustomer, useKycProfile, useDocuments } from "@/hooks/usePortalData";
import { useAuth } from "@/context/AuthContext";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { apiRequest } from "@/lib/api";
import type { RiskScore } from "@/lib/types";
import { cn, formatDate, getStatusColor, getRiskColor } from "@/lib/utils";

// ─── Task Types ───────────────────────────────────────────────────────────────
type Task = {
  id: string;
  label: string;
  description: string;
  href: string;
  done: boolean;
  priority: "high" | "medium" | "low";
};

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  colorClass,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  colorClass: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className={cn("rounded-xl border p-5 shadow-sm transition-shadow hover:shadow-md", colorClass)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest opacity-70">{label}</p>
          <p className="mt-2 text-2xl font-bold capitalize leading-none">{value}</p>
          {sub && <p className="mt-1 text-xs opacity-60">{sub}</p>}
        </div>
        <div className="rounded-lg bg-white/30 p-2">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

// ─── Progress Ring ────────────────────────────────────────────────────────────
function ProgressRing({ pct }: { pct: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width="72" height="72" viewBox="0 0 72 72">
      <circle cx="36" cy="36" r={r} fill="none" stroke="#e4e4e7" strokeWidth="6" />
      <circle
        cx="36" cy="36" r={r} fill="none"
        stroke="#0f766e" strokeWidth="6"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 36 36)"
        className="transition-all duration-700"
      />
      <text x="36" y="40" textAnchor="middle" className="text-[11px] font-bold fill-zinc-800">
        {pct}%
      </text>
    </svg>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export default function CustomerDashboard() {
  const { user } = useAuth();
  const { token } = useAuth();
  const { data: customer, isLoading: custLoading } = useCustomer();
  const { data: kyc } = useKycProfile(customer?.id);
  const { data: documents } = useDocuments(customer?.id);
  const { completionPercent, draft } = useOnboardingDraft();
  const [riskScore, setRiskScore] = useState<RiskScore | null>(null);

  useEffect(() => {
    if (!customer?.id || !token) return;
    apiRequest<RiskScore[]>(`/risk-scores/customer/${customer.id}`, {}, token)
      .then((scores) => { if (scores.length > 0) setRiskScore(scores[0]); })
      .catch(() => { /* not yet available */ });
  }, [customer?.id, token]);

  const tasks: Task[] = [
    {
      id: "profile",
      label: "Complete Your Profile",
      description: "Add personal details, address, and contact information",
      href: "/customer/onboarding/profile",
      done: draft.profileComplete,
      priority: "high",
    },
    {
      id: "kyc",
      label: "Submit KYC Declaration",
      description: "Provide occupation, source of funds and wealth information",
      href: "/customer/onboarding/kyc",
      done: draft.kycComplete,
      priority: "high",
    },
    {
      id: "documents",
      label: "Upload Identity Documents",
      description: "Upload passport, national ID or driving licence",
      href: "/customer/onboarding/documents",
      done: draft.documentsComplete,
      priority: "high",
    },
    ...(draft.customerType === "corporate"
      ? [{
          id: "company",
          label: "Submit Company Details",
          description: "Add directors, UBOs, and shareholder information",
          href: "/customer/onboarding/company",
          done: draft.companyComplete,
          priority: "medium" as const,
        }]
      : []),
    {
      id: "review",
      label: "Review & Submit Application",
      description: "Confirm all information and submit for AML screening",
      href: "/customer/onboarding/review",
      done: customer?.status !== "onboarding" && customer?.status !== "pending_verification",
      priority: "medium",
    },
  ];

  const pendingTasks = tasks.filter((t) => !t.done);
  const completedTasks = tasks.filter((t) => t.done);

  const stats = [
    {
      label: "Application Status",
      value: (customer?.status || "Loading").replace(/_/g, " "),
      sub: formatDate(customer?.created_at),
      colorClass: getStatusColor(customer?.status || ""),
      icon: Gauge,
    },
    {
      label: "AML Risk Tier",
      value: riskScore?.risk_tier || kyc?.risk_category || "Not screened",
      sub: riskScore ? `Score: ${riskScore.overall_score.toFixed(0)} / 100` : "Awaiting submission",
      colorClass: getRiskColor(riskScore?.risk_tier || kyc?.risk_category || ""),
      icon: Shield,
    },
    {
      label: "Documents",
      value: String(documents?.length ?? 0),
      sub: `${documents?.filter((d) => d.verification_status === "verified").length ?? 0} verified`,
      colorClass: "bg-white border-zinc-200 text-zinc-800",
      icon: FileCheck,
    },
    {
      label: "Profile Type",
      value: customer?.customer_type || "Individual",
      sub: customer?.nationality || "—",
      colorClass: "bg-white border-zinc-200 text-zinc-800",
      icon: UserRound,
    },
  ];

  if (custLoading) {
    return (
      <ProtectedRoute>
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-teal-600" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="space-y-6 animate-fade-in">
        {(user?.role === "compliance_officer" || user?.role === "admin") && (
          <div className="flex items-center justify-between rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-indigo-900 shadow-sm">
            <div className="flex items-center gap-3">
              <Shield className="h-5 w-5 text-indigo-600 shrink-0" />
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-indigo-700">Officer / Administrator View</p>
                <p className="text-sm font-medium">You are currently previewing the Customer KYC Portal as <span className="font-bold">{user.email}</span> ({user.role.replace("_", " ")}).</p>
              </div>
            </div>
            <Link
              href="/admin"
              className="flex items-center gap-1.5 rounded-lg bg-indigo-700 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-800 transition-colors shadow-sm"
            >
              Open Officer Panel <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}

        {/* Welcome Banner */}
        <div className="rounded-xl border border-teal-100 bg-gradient-to-r from-teal-700 to-teal-800 p-6 text-white shadow-md">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium text-teal-200">Welcome back</p>
              <h1 className="mt-1 text-2xl font-bold">
                {customer?.first_name
                  ? `${customer.first_name} ${customer.last_name || ""}`.trim()
                  : user?.email?.split("@")[0] || "Customer"}
              </h1>
              <p className="mt-1 text-sm text-teal-200">
                {customer?.status === "approved"
                  ? "✓ Your KYC application has been approved"
                  : customer?.status === "referred"
                  ? "⚠ Your application is under manual review"
                  : "Complete your onboarding to activate your account"}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex flex-col items-center">
                <ProgressRing pct={completionPercent} />
                <p className="mt-1 text-[11px] text-teal-200">Complete</p>
              </div>
              {pendingTasks.length > 0 && (
                <Link
                  href={pendingTasks[0].href}
                  className="flex items-center gap-2 rounded-lg bg-white/20 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/30 transition-colors"
                >
                  Continue <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>

        <div className="grid gap-5 lg:grid-cols-5">
          {/* Outstanding Tasks — Left (3 cols) */}
          <div className="space-y-4 lg:col-span-3">

            {/* Pending Tasks */}
            {pendingTasks.length > 0 && (
              <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    <h2 className="text-sm font-semibold text-zinc-800">Outstanding Tasks</h2>
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-700">
                      {pendingTasks.length}
                    </span>
                  </div>
                </div>
                <div className="divide-y divide-zinc-50">
                  {pendingTasks.map((task) => (
                    <Link
                      key={task.id}
                      href={task.href}
                      className="flex items-center justify-between px-5 py-3.5 hover:bg-zinc-50 transition-colors group"
                    >
                      <div className="flex items-start gap-3">
                        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-zinc-300" />
                        <div>
                          <p className="text-sm font-medium text-zinc-800 group-hover:text-teal-700 transition-colors">
                            {task.label}
                          </p>
                          <p className="text-xs text-zinc-500">{task.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {task.priority === "high" && (
                          <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-600 border border-red-100">
                            Required
                          </span>
                        )}
                        <ArrowRight className="h-4 w-4 text-zinc-300 group-hover:text-teal-600 transition-colors" />
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Completed Tasks */}
            {completedTasks.length > 0 && (
              <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
                <div className="flex items-center gap-2 border-b border-zinc-100 px-5 py-3">
                  <CheckCircle className="h-4 w-4 text-emerald-500" />
                  <h2 className="text-sm font-semibold text-zinc-800">Completed</h2>
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-700">
                    {completedTasks.length}
                  </span>
                </div>
                <div className="divide-y divide-zinc-50">
                  {completedTasks.map((task) => (
                    <div key={task.id} className="flex items-center gap-3 px-5 py-3">
                      <CheckCircle className="h-4 w-4 shrink-0 text-emerald-500" />
                      <div>
                        <p className="text-sm font-medium text-zinc-500 line-through">{task.label}</p>
                        <p className="text-xs text-zinc-400">{task.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* All done */}
            {pendingTasks.length === 0 && (
              <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
                <CheckCircle className="h-8 w-8 text-emerald-600" />
                <div>
                  <p className="font-semibold text-emerald-800">All steps complete!</p>
                  <p className="text-sm text-emerald-700">Your application is being processed by our AML team.</p>
                </div>
                <Link
                  href="/customer/status"
                  className="ml-auto flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
                >
                  Track Status <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
          </div>

          {/* Right Panel (2 cols) */}
          <div className="space-y-4 lg:col-span-2">

            {/* Quick Actions */}
            <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
              <div className="border-b border-zinc-100 px-4 py-3">
                <h2 className="text-sm font-semibold text-zinc-800">Quick Actions</h2>
              </div>
              <div className="grid grid-cols-2 gap-2 p-4">
                {[
                  { href: "/customer/onboarding/profile", label: "Edit Profile", icon: UserRound },
                  { href: "/customer/onboarding/kyc", label: "Update KYC", icon: FileText },
                  { href: "/customer/onboarding/documents", label: "Upload Docs", icon: Upload },
                  { href: "/customer/status", label: "View Status", icon: Activity },
                ].map((action) => {
                  const Icon = action.icon;
                  return (
                    <Link
                      key={action.href}
                      href={action.href}
                      className="flex flex-col items-center gap-1.5 rounded-lg border border-zinc-100 p-3 text-center hover:border-teal-200 hover:bg-teal-50 transition-all group"
                    >
                      <Icon className="h-5 w-5 text-zinc-400 group-hover:text-teal-600 transition-colors" />
                      <span className="text-[11px] font-medium text-zinc-600 group-hover:text-teal-700">{action.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* Risk Breakdown */}
            {riskScore && (
              <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
                <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3">
                  <TrendingUp className="h-4 w-4 text-zinc-500" />
                  <h2 className="text-sm font-semibold text-zinc-800">Risk Breakdown</h2>
                </div>
                <div className="space-y-2.5 p-4">
                  {Object.entries(riskScore.breakdown).map(([key, score]) => {
                    const maxes: Record<string, number> = { pep: 25, sanctions: 35, country: 20, document: 20, transaction: 20 };
                    const max = maxes[key] ?? 20;
                    const pct = (score / max) * 100;
                    return (
                      <div key={key}>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="capitalize text-zinc-600">{key.replace(/_/g, " ")}</span>
                          <span className={cn("font-semibold", score > 0 ? "text-red-600" : "text-emerald-600")}>
                            {score}/{max}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-zinc-100">
                          <div
                            className={cn("h-1.5 rounded-full transition-all duration-700",
                              score > max * 0.6 ? "bg-red-400" : score > 0 ? "bg-amber-400" : "bg-emerald-400"
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

            {/* Application Timeline Snapshot */}
            <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
              <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3">
                <Zap className="h-4 w-4 text-zinc-500" />
                <h2 className="text-sm font-semibold text-zinc-800">Current Stage</h2>
              </div>
              <div className="p-4">
                {[
                  { label: "Profile", done: draft.profileComplete },
                  { label: "KYC", done: draft.kycComplete },
                  { label: "Documents", done: draft.documentsComplete },
                  { label: "Review", done: customer?.status !== "onboarding" },
                  { label: "Screening", done: !!riskScore },
                ].map((step, i, arr) => (
                  <div key={step.label} className="flex items-center gap-3">
                    <div className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                      step.done ? "bg-teal-600 text-white" : "bg-zinc-100 text-zinc-400"
                    )}>
                      {step.done ? <CheckCircle className="h-3.5 w-3.5" /> : i + 1}
                    </div>
                    <span className={cn("text-xs font-medium", step.done ? "text-teal-700" : "text-zinc-400")}>
                      {step.label}
                    </span>
                    {i < arr.length - 1 && (
                      <div className={cn("ml-auto mr-2 h-0.5 flex-1", step.done ? "bg-teal-200" : "bg-zinc-100")} />
                    )}
                  </div>
                ))}
              </div>
              <div className="border-t border-zinc-100 px-4 py-3">
                <Link href="/customer/status" className="flex items-center gap-1.5 text-xs font-medium text-teal-700 hover:text-teal-800">
                  <Activity className="h-3.5 w-3.5" /> View full timeline
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
