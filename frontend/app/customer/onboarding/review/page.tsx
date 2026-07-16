"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import Link from "next/link";
import {
  ClipboardCheck, UserRound, FileText, Upload, Building2,
  Edit2, CheckCircle, AlertCircle, ArrowLeft, Send,
} from "lucide-react";
import { useCustomer, useKycProfile, useDocuments } from "@/hooks/usePortalData";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { cn, formatDate, getStatusColor } from "@/lib/utils";

export default function ReviewStep() {
  const router = useRouter();
  const { token } = useAuth();
  const { data: customer, isLoading: custLoading } = useCustomer();
  const { data: kyc, isLoading: kycLoading } = useKycProfile(customer?.id);
  const { data: documents } = useDocuments(customer?.id);
  const { draft, clearDraft } = useOnboardingDraft();

  const isLoading = custLoading || kycLoading;

  const sections = [
    {
      title: "Customer Profile",
      icon: UserRound,
      editHref: "/customer/onboarding/profile",
      complete: draft.profileComplete,
      items: customer
        ? [
            { label: "Name", value: `${customer.first_name || ""} ${customer.last_name || ""}`.trim() || "—" },
            { label: "Type", value: customer.customer_type || "—" },
            { label: "DOB", value: formatDate(customer.dob) },
            { label: "Nationality", value: customer.nationality || "—" },
            { label: "Phone", value: customer.phone_number || "—" },
            { label: "Country", value: customer.country || "—" },
          ]
        : [],
    },
    {
      title: "KYC Declaration",
      icon: FileText,
      editHref: "/customer/onboarding/kyc",
      complete: draft.kycComplete,
      items: kyc
        ? [
            { label: "Full Name", value: kyc.full_name || "—" },
            { label: "Nationality", value: kyc.nationality || "—" },
            { label: "Tax Residency", value: kyc.tax_residency || "—" },
            { label: "Occupation", value: kyc.occupation || "—" },
            { label: "Source of Funds", value: kyc.source_of_funds || "—" },
            { label: "Annual Income", value: kyc.annual_income_range || "—" },
          ]
        : [],
    },
    {
      title: "Documents",
      icon: Upload,
      editHref: "/customer/onboarding/documents",
      complete: draft.documentsComplete,
      items: documents
        ? documents.map((d) => ({
            label: d.document_type.replace(/_/g, " "),
            value: `${d.file_name} (${d.verification_status})`,
          }))
        : [{ label: "Status", value: "No documents uploaded" }],
    },
    ...(draft.customerType === "corporate"
      ? [
          {
            title: "Company Details",
            icon: Building2,
            editHref: "/customer/onboarding/company",
            complete: draft.companyComplete,
            items: [{ label: "Status", value: draft.companyComplete ? "Company details submitted" : "Not completed" }],
          },
        ]
      : []),
  ];

  const allComplete = draft.profileComplete && draft.kycComplete && draft.documentsComplete &&
    (draft.customerType !== "corporate" || draft.companyComplete);

  const handleSubmit = async () => {
    if (!customer?.id || !token) return;
    try {
      // Trigger AML screening via KYC update
      await apiRequest(
        `/kyc/${customer.id}`,
        { method: "PUT", body: JSON.stringify({ risk_category: "low" }) },
        token
      );
      clearDraft();
      toast.success("Application submitted for AML screening");
      router.push("/customer/status");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Submission failed");
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-zinc-200 bg-white">
        <div className="h-7 w-7 animate-spin rounded-full border-b-2 border-teal-600" />
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
          <ClipboardCheck className="h-5 w-5 text-teal-700" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Review & Submit</h1>
          <p className="text-sm text-zinc-500">Step 5 of 5 — Verify all information before submitting for AML screening</p>
        </div>
      </div>

      {/* Sections */}
      {sections.map((section) => {
        const Icon = section.icon;
        return (
          <div key={section.title} className="rounded-xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-zinc-500" />
                <h2 className="text-sm font-semibold text-zinc-800">{section.title}</h2>
              </div>
              <div className="flex items-center gap-3">
                {section.complete ? (
                  <span className="flex items-center gap-1 text-xs text-emerald-600">
                    <CheckCircle className="h-3.5 w-3.5" /> Complete
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs text-amber-600">
                    <AlertCircle className="h-3.5 w-3.5" /> Incomplete
                  </span>
                )}
                <Link
                  href={section.editHref}
                  className="flex items-center gap-1 rounded-md border border-zinc-200 px-2.5 py-1 text-xs text-zinc-600 hover:bg-zinc-50 transition-colors"
                >
                  <Edit2 className="h-3 w-3" /> Edit
                </Link>
              </div>
            </div>
            <div className="grid gap-x-6 gap-y-2 px-5 py-4 sm:grid-cols-2 lg:grid-cols-3">
              {section.items.map((item) => (
                <div key={item.label}>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{item.label}</p>
                  <p className="mt-0.5 text-sm text-zinc-800 capitalize">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {/* Warning if incomplete */}
      {!allComplete && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-amber-800">Application incomplete</p>
            <p className="text-xs text-amber-700 mt-0.5">
              Please complete all required sections before submitting. Incomplete sections are highlighted above.
            </p>
          </div>
        </div>
      )}

      {/* Declaration */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-zinc-800 mb-2">Declaration</h3>
        <p className="text-xs text-zinc-500 leading-relaxed">
          By submitting this application, I confirm that all information provided is true, accurate, and complete to the best of my knowledge. I understand that providing false or misleading information may constitute a criminal offence under the Fraud Act 2006. I consent to my information being processed for AML and KYC compliance purposes as required by the Money Laundering, Terrorist Financing and Transfer of Funds (Information on the Payer) Regulations 2017.
        </p>
      </div>

      {/* Customer status badge */}
      {customer?.status && (
        <div className={cn("flex items-center gap-2 rounded-xl border p-4", getStatusColor(customer.status))}>
          <p className="text-xs font-semibold">Current Status: <span className="capitalize">{customer.status.replace(/_/g, " ")}</span></p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/customer/onboarding/company")}
          className="flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!allComplete}
          className={cn(
            "flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-bold text-white transition-all",
            allComplete
              ? "bg-teal-700 hover:bg-teal-800 shadow-md hover:shadow-lg"
              : "bg-zinc-300 cursor-not-allowed"
          )}
        >
          <Send className="h-4 w-4" /> Submit Application
        </button>
      </div>
    </div>
  );
}
