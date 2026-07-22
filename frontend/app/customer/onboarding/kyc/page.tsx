"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { FileText, ArrowLeft, ArrowRight, Info } from "lucide-react";
import {
  kycSchema,
  type KycFormData,
  SOURCE_OF_FUNDS_OPTIONS,
  ANNUAL_INCOME_OPTIONS,
} from "@/lib/types";
import { useCustomer, useKycProfile } from "@/hooks/usePortalData";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { cn } from "@/lib/utils";

const COUNTRIES = [
  "United Kingdom", "United States", "Canada", "Australia", "Germany",
  "France", "Spain", "Italy", "Netherlands", "India", "Singapore", "UAE",
  "South Africa", "Nigeria", "Other",
];

export default function KycStep() {
  const router = useRouter();
  const { data: customer } = useCustomer();
  const { data: kycProfile, isLoading, hasProfile, create, update } = useKycProfile(customer?.id);
  const { markStepComplete } = useOnboardingDraft();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  // eslint-disable-next-line
  } = useForm<KycFormData, any, KycFormData>({
    resolver: zodResolver(kycSchema) as any,
    defaultValues: {
      full_name: "",
      dob: "",
      nationality: "",
      tax_residency: "",
      address: "",
      occupation: "",
      source_of_funds: "",
      source_of_wealth: "",
      annual_income_range: "",
      expected_activity_desc: "",
      risk_category: "low",
    },
  });

  useEffect(() => {
    if (kycProfile) {
      reset({
        full_name: kycProfile.full_name || "",
        dob: kycProfile.dob || "",
        nationality: kycProfile.nationality || "",
        tax_residency: kycProfile.tax_residency || "",
        address: kycProfile.address || "",
        occupation: kycProfile.occupation || "",
        source_of_funds: kycProfile.source_of_funds || "",
        source_of_wealth: kycProfile.source_of_wealth || "",
        annual_income_range: kycProfile.annual_income_range || "",
        expected_activity_desc: kycProfile.expected_activity_desc || "",
        risk_category: (kycProfile.risk_category as "low" | "medium" | "high") || "low",
      });
    } else if (customer) {
      reset({
        full_name: `${customer.first_name || ""} ${customer.last_name || ""}`.trim(),
        dob: customer.dob || "",
        nationality: customer.nationality || "",
        tax_residency: "",
        address: `${customer.street_address || ""}, ${customer.city || ""}, ${customer.postal_code || ""}`.trim().replace(/^,\s*/, "").replace(/,\s*,/g, ","),
        occupation: "",
        source_of_funds: "",
        source_of_wealth: "",
        annual_income_range: "",
        expected_activity_desc: "",
        risk_category: "low",
      });
    }
  }, [kycProfile, customer, reset]);

  const onSubmit = async (data: KycFormData) => {
    if (!customer?.id) {
      toast.error("Customer profile not found. Please complete Step 1 first.");
      return;
    }
    try {
      const payload = {
        customer_id: customer.id,
        full_name: data.full_name,
        dob: data.dob,
        nationality: data.nationality,
        tax_residency: data.tax_residency,
        address: data.address,
        occupation: data.occupation,
        source_of_funds: data.source_of_funds,
        source_of_wealth: data.source_of_wealth,
        annual_income_range: data.annual_income_range,
        expected_activity_desc: data.expected_activity_desc,
        risk_category: data.risk_category,
      };

      if (hasProfile) {
        await update.mutateAsync(payload);
      } else {
        await create.mutateAsync(payload);
      }

      markStepComplete("kyc");
      toast.success("KYC profile saved successfully");
      router.push("/customer/onboarding/documents");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "KYC submission failed");
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
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
          <FileText className="h-5 w-5 text-teal-700" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-900">KYC Declaration</h1>
          <p className="text-sm text-zinc-500">Step 2 of 5 — Know Your Customer information for AML screening</p>
        </div>
      </div>

      {/* Section 1: Identity */}
      <Section title="Identity & Nationality">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full Legal Name" error={errors.full_name?.message} required>
            <input {...register("full_name")} placeholder="As shown on ID document" className={inputCls(!!errors.full_name)} />
          </Field>
          <Field label="Date of Birth" error={errors.dob?.message} required>
            <input type="date" {...register("dob")} className={inputCls(!!errors.dob)} />
          </Field>
          <Field label="Nationality" error={errors.nationality?.message} required>
            <select {...register("nationality")} className={inputCls(!!errors.nationality)}>
              <option value="">Select nationality</option>
              {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Tax Residency Country" error={errors.tax_residency?.message} required hint="Country where you pay primary taxes">
            <select {...register("tax_residency")} className={inputCls(!!errors.tax_residency)}>
              <option value="">Select country</option>
              {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
        </div>
      </Section>

      {/* Section 2: Address */}
      <Section title="Residential Address">
        <Field label="Full Residential Address" error={errors.address?.message} required>
          <textarea
            {...register("address")}
            rows={3}
            placeholder="Full address including street, city, postcode and country"
            className={inputCls(!!errors.address)}
          />
        </Field>
      </Section>

      {/* Section 3: Occupation & Wealth */}
      <Section title="Occupation & Financial Profile">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Occupation / Job Title" error={errors.occupation?.message} required>
            <input {...register("occupation")} placeholder="e.g. Software Engineer, Director" className={inputCls(!!errors.occupation)} />
          </Field>
          <Field label="Annual Income Range" error={errors.annual_income_range?.message} required hint="Gross annual income before tax">
            <select {...register("annual_income_range")} className={inputCls(!!errors.annual_income_range)}>
              <option value="">Select range</option>
              {ANNUAL_INCOME_OPTIONS.map((o) => <option key={o}>{o}</option>)}
            </select>
          </Field>
          <Field label="Primary Source of Funds" error={errors.source_of_funds?.message} required hint="How money enters your account">
            <select {...register("source_of_funds")} className={inputCls(!!errors.source_of_funds)}>
              <option value="">Select source</option>
              {SOURCE_OF_FUNDS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Source of Wealth" error={errors.source_of_wealth?.message} required hint="Explain how you accumulated your overall wealth">
          <textarea
            {...register("source_of_wealth")}
            rows={4}
            placeholder="Describe how you have accumulated your overall net worth (e.g. 20 years in technology sector, sale of property in 2021, inheritance from estate...)"
            className={inputCls(!!errors.source_of_wealth)}
          />
          {!errors.source_of_wealth && (
            <p className="mt-1 text-[11px] text-zinc-400">Minimum 20 characters required for compliance</p>
          )}
        </Field>
      </Section>

      {/* Section 4: Expected Activity */}
      <Section title="Expected Account Activity">
        <Field label="Expected Account Activity" error={errors.expected_activity_desc?.message} required hint="Describe typical transaction patterns">
          <textarea
            {...register("expected_activity_desc")}
            rows={3}
            placeholder="e.g. Monthly salary credits of £5,000, occasional international transfers to family, quarterly investment purchases..."
            className={inputCls(!!errors.expected_activity_desc)}
          />
        </Field>
        <div className="mt-3 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <Info className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
          <p className="text-xs text-amber-700">
            This information is used solely for AML compliance screening as required by UK Money Laundering Regulations 2017 (as amended through 2024/2026) & ECCTA 2023. All data is handled under our Privacy Policy.
          </p>
        </div>
      </Section>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/customer/onboarding/profile")}
          className="flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex items-center gap-2 rounded-lg bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60 transition-colors"
        >
          {isSubmitting ? (
            <span className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
          ) : (
            <>{hasProfile ? "Update KYC" : "Save KYC"} <ArrowRight className="h-4 w-4" /></>
          )}
        </button>
      </div>
    </form>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold text-zinc-700 border-b border-zinc-100 pb-2">{title}</h2>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function inputCls(hasError: boolean) {
  return cn(
    "w-full rounded-lg border px-3 py-2.5 text-sm outline-none transition-all",
    hasError
      ? "border-red-300 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100"
      : "border-zinc-300 bg-white focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
  );
}

function Field({
  label,
  error,
  required,
  hint,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div>
        <label className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          {label}
          {required && <span className="text-red-500">*</span>}
        </label>
        {hint && <p className="text-[11px] text-zinc-400">{hint}</p>}
      </div>
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
