"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import {
  Building2, ArrowLeft, ArrowRight, Plus, Trash2, Users, Briefcase,
} from "lucide-react";
import { companySchema, type CompanyFormData, INDUSTRY_OPTIONS, TURNOVER_OPTIONS, SOURCE_OF_FUNDS_OPTIONS } from "@/lib/types";
import { useCustomer, useCompany } from "@/hooks/usePortalData";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";

const COUNTRIES = [
  "United Kingdom","United States","Canada","Australia","Germany","France",
  "Spain","Italy","Netherlands","India","Singapore","UAE","Other",
];

export default function CompanyStep() {
  const router = useRouter();
  const { token } = useAuth();
  const { data: customer } = useCustomer();
  const { data: companyData, isLoading: companyLoading } = useCompany();
  const { markStepComplete } = useOnboardingDraft();
  const [activeTab, setActiveTab] = useState<"company" | "directors" | "ubos" | "shareholders">("company");

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  // eslint-disable-next-line
  } = useForm<CompanyFormData, any, CompanyFormData>({
    resolver: zodResolver(companySchema) as any,
    defaultValues: {
      company_name: "",
      registration_number: "",
      registered_address: "",
      trading_address: "",
      country_of_incorporation: "United Kingdom",
      incorporation_date: "",
      sic_code: "",
      industry: "",
      tax_number: "",
      expected_turnover: "",
      source_of_funds: "",
      directors: [{ first_name: "", last_name: "", dob: "", nationality: "", appointment_date: "" }],
      ubos: [],
      shareholders: [],
    },
  });

  // Pre-populate form when companyData loads
  useEffect(() => {
    if (companyData) {
      reset({
        company_name: companyData.company?.company_name || "",
        registration_number: companyData.company?.registration_number || "",
        registered_address: companyData.company?.registered_address || "",
        trading_address: companyData.company?.trading_address || "",
        country_of_incorporation: companyData.company?.country_of_incorporation || "United Kingdom",
        incorporation_date: companyData.company?.incorporation_date || "",
        sic_code: companyData.company?.sic_code || "",
        industry: companyData.company?.industry || "",
        tax_number: companyData.company?.tax_number || "",
        expected_turnover: companyData.company?.expected_turnover || "",
        source_of_funds: companyData.company?.source_of_funds || "",
        directors: companyData.directors?.length
          ? companyData.directors.map((d: any) => ({
              first_name: d.first_name || "",
              last_name: d.last_name || "",
              dob: d.dob || "",
              nationality: d.nationality || "",
              appointment_date: d.appointment_date || "",
            }))
          : [{ first_name: "", last_name: "", dob: "", nationality: "", appointment_date: "" }],
        ubos: companyData.ubos?.map((u: any) => ({
          first_name: u.first_name || "",
          last_name: u.last_name || "",
          dob: u.dob || "",
          nationality: u.nationality || "",
          ownership_percentage: u.ownership_percentage || 0,
          control_type: u.control_type || "",
        })) || [],
        shareholders: [],
      });
    }
  }, [companyData, reset]);

  const directors = useFieldArray({ control, name: "directors" });
  const ubos = useFieldArray({ control, name: "ubos" });
  const shareholders = useFieldArray({ control, name: "shareholders" });

  const onSubmit = async (data: CompanyFormData) => {
    if (!customer?.id || !token) return;
    try {
      await apiRequest(
        "/customers/",
        {
          method: "POST",
          body: JSON.stringify({
            customer_type: "corporate",
            company: {
              company_name: data.company_name,
              registration_number: data.registration_number,
              registered_address: data.registered_address,
              trading_address: data.trading_address,
              country_of_incorporation: data.country_of_incorporation,
              incorporation_date: data.incorporation_date || undefined,
              sic_code: data.sic_code || undefined,
            },
            directors: data.directors.map((d) => ({
              first_name: d.first_name,
              last_name: d.last_name,
              dob: d.dob || undefined,
              nationality: d.nationality || undefined,
              appointment_date: d.appointment_date || undefined,
            })),
            ubos: data.ubos.map((u) => ({
              first_name: u.first_name,
              last_name: u.last_name,
              dob: u.dob || undefined,
              nationality: u.nationality || undefined,
              ownership_percentage: u.ownership_percentage,
              control_type: u.control_type,
            })),
          }),
        },
        token
      );
      markStepComplete("company");
      toast.success("Company details saved");
      router.push("/customer/onboarding/review");
    } catch (err) {
      // If company already exists, still allow navigation
      if (err instanceof Error && err.message.includes("already exists")) {
        markStepComplete("company");
        router.push("/customer/onboarding/review");
      } else {
        toast.error(err instanceof Error ? err.message : "Failed to save company details");
      }
    }
  };

  const tabs = [
    { id: "company" as const, label: "Company", icon: Building2, count: null },
    { id: "directors" as const, label: "Directors", icon: Briefcase, count: directors.fields.length },
    { id: "ubos" as const, label: "UBOs", icon: Users, count: ubos.fields.length },
    { id: "shareholders" as const, label: "Shareholders", icon: Users, count: shareholders.fields.length },
  ];

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
          <Building2 className="h-5 w-5 text-teal-700" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Company Details</h1>
          <p className="text-sm text-zinc-500">Step 4 of 5 — Corporate structure, directors, UBOs, and shareholders</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="rounded-xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        <div className="flex border-b border-zinc-200">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1.5 py-3 text-xs font-semibold transition-colors",
                  activeTab === tab.id
                    ? "border-b-2 border-teal-600 text-teal-700 bg-teal-50"
                    : "text-zinc-500 hover:bg-zinc-50"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
                {tab.count !== null && tab.count > 0 && (
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-teal-600 text-[9px] text-white">
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="p-5">
          {/* Company Tab */}
          {activeTab === "company" && (
            <div className="space-y-4 animate-fade-in">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Company Name" error={(errors.company_name as { message?: string })?.message} required>
                  <input {...register("company_name")} placeholder="Acme Ltd" className={inputCls(!!errors.company_name)} />
                </Field>
                <Field label="Registration Number" error={(errors.registration_number as { message?: string })?.message} required>
                  <input {...register("registration_number")} placeholder="12345678" className={inputCls(!!errors.registration_number)} />
                </Field>
                <Field label="Country of Incorporation" error={(errors.country_of_incorporation as { message?: string })?.message} required>
                  <select {...register("country_of_incorporation")} className={inputCls(!!errors.country_of_incorporation)}>
                    {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </Field>
                <Field label="Date of Incorporation" error={(errors.incorporation_date as { message?: string })?.message}>
                  <input type="date" {...register("incorporation_date")} className={inputCls(!!errors.incorporation_date)} />
                </Field>
                <Field label="Industry / Sector" error={(errors.industry as { message?: string })?.message} required>
                  <select {...register("industry")} className={inputCls(!!errors.industry)}>
                    <option value="">Select industry</option>
                    {INDUSTRY_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </select>
                </Field>
                <Field label="SIC Code" error={(errors.sic_code as { message?: string })?.message}>
                  <input {...register("sic_code")} placeholder="62012" className={inputCls(!!errors.sic_code)} />
                </Field>
                <Field label="Tax Reference Number" error={(errors.tax_number as { message?: string })?.message}>
                  <input {...register("tax_number")} placeholder="UTR or VAT number" className={inputCls(!!errors.tax_number)} />
                </Field>
                <Field label="Expected Annual Turnover" error={(errors.expected_turnover as { message?: string })?.message} required>
                  <select {...register("expected_turnover")} className={inputCls(!!errors.expected_turnover)}>
                    <option value="">Select range</option>
                    {TURNOVER_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </select>
                </Field>
                <Field label="Company Source of Funds" error={(errors.source_of_funds as { message?: string })?.message} required>
                  <select {...register("source_of_funds")} className={inputCls(!!errors.source_of_funds)}>
                    <option value="">Select source</option>
                    {SOURCE_OF_FUNDS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </select>
                </Field>
              </div>
              <Field label="Registered Address" error={(errors.registered_address as { message?: string })?.message} required>
                <textarea {...register("registered_address")} rows={2} placeholder="Full registered address" className={inputCls(!!errors.registered_address)} />
              </Field>
              <Field label="Trading Address (if different)">
                <textarea {...register("trading_address")} rows={2} placeholder="Leave blank if same as registered address" className={inputCls(false)} />
              </Field>
            </div>
          )}

          {/* Directors Tab */}
          {activeTab === "directors" && (
            <div className="space-y-4 animate-fade-in">
              {directors.fields.map((field, i) => (
                <div key={field.id} className="relative rounded-lg border border-zinc-200 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold text-zinc-600">Director {i + 1}</p>
                    {directors.fields.length > 1 && (
                      <button type="button" onClick={() => directors.remove(i)} className="text-red-500 hover:text-red-700">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="First Name" error={errors.directors?.[i]?.first_name?.message} required>
                      <input {...register(`directors.${i}.first_name`)} className={inputCls(!!errors.directors?.[i]?.first_name)} />
                    </Field>
                    <Field label="Last Name" error={errors.directors?.[i]?.last_name?.message} required>
                      <input {...register(`directors.${i}.last_name`)} className={inputCls(!!errors.directors?.[i]?.last_name)} />
                    </Field>
                    <Field label="Date of Birth">
                      <input type="date" {...register(`directors.${i}.dob`)} className={inputCls(false)} />
                    </Field>
                    <Field label="Nationality">
                      <select {...register(`directors.${i}.nationality`)} className={inputCls(false)}>
                        <option value="">Select</option>
                        {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
                      </select>
                    </Field>
                    <Field label="Appointment Date">
                      <input type="date" {...register(`directors.${i}.appointment_date`)} className={inputCls(false)} />
                    </Field>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => directors.append({ first_name: "", last_name: "", dob: "", nationality: "", appointment_date: "" })}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-300 py-3 text-sm text-zinc-500 hover:border-teal-300 hover:text-teal-700 transition-colors"
              >
                <Plus className="h-4 w-4" /> Add Director
              </button>
            </div>
          )}

          {/* UBOs Tab */}
          {activeTab === "ubos" && (
            <div className="space-y-4 animate-fade-in">
              <p className="text-xs text-zinc-500">Ultimate Beneficial Owners (UBOs) are individuals who own or control 25% or more of the company.</p>
              {ubos.fields.map((field, i) => (
                <div key={field.id} className="relative rounded-lg border border-zinc-200 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold text-zinc-600">UBO {i + 1}</p>
                    <button type="button" onClick={() => ubos.remove(i)} className="text-red-500 hover:text-red-700">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="First Name" error={errors.ubos?.[i]?.first_name?.message} required>
                      <input {...register(`ubos.${i}.first_name`)} className={inputCls(!!errors.ubos?.[i]?.first_name)} />
                    </Field>
                    <Field label="Last Name" error={errors.ubos?.[i]?.last_name?.message} required>
                      <input {...register(`ubos.${i}.last_name`)} className={inputCls(!!errors.ubos?.[i]?.last_name)} />
                    </Field>
                    <Field label="Ownership %" error={errors.ubos?.[i]?.ownership_percentage?.message} required>
                      <input type="number" step="0.01" min="0" max="100" {...register(`ubos.${i}.ownership_percentage`, { valueAsNumber: true })} className={inputCls(!!errors.ubos?.[i]?.ownership_percentage)} />
                    </Field>
                    <Field label="Control Type" error={errors.ubos?.[i]?.control_type?.message} required>
                      <select {...register(`ubos.${i}.control_type`)} className={inputCls(!!errors.ubos?.[i]?.control_type)}>
                        <option value="">Select</option>
                        <option value="direct_ownership">Direct Ownership</option>
                        <option value="indirect_ownership">Indirect Ownership</option>
                        <option value="voting_rights">Voting Rights</option>
                        <option value="other">Other Means of Control</option>
                      </select>
                    </Field>
                    <Field label="Nationality">
                      <select {...register(`ubos.${i}.nationality`)} className={inputCls(false)}>
                        <option value="">Select</option>
                        {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
                      </select>
                    </Field>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => ubos.append({ first_name: "", last_name: "", ownership_percentage: 25, control_type: "", dob: "", nationality: "" })}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-300 py-3 text-sm text-zinc-500 hover:border-teal-300 hover:text-teal-700 transition-colors"
              >
                <Plus className="h-4 w-4" /> Add UBO
              </button>
            </div>
          )}

          {/* Shareholders Tab */}
          {activeTab === "shareholders" && (
            <div className="space-y-4 animate-fade-in">
              <p className="text-xs text-zinc-500">List all significant shareholders (holding 10% or more).</p>
              {shareholders.fields.map((field, i) => (
                <div key={field.id} className="relative rounded-lg border border-zinc-200 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold text-zinc-600">Shareholder {i + 1}</p>
                    <button type="button" onClick={() => shareholders.remove(i)} className="text-red-500 hover:text-red-700">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Name / Entity" error={errors.shareholders?.[i]?.name?.message} required>
                      <input {...register(`shareholders.${i}.name`)} placeholder="John Smith or Acme Holdings Ltd" className={inputCls(!!errors.shareholders?.[i]?.name)} />
                    </Field>
                    <Field label="Share %" error={errors.shareholders?.[i]?.share_percentage?.message} required>
                      <input type="number" step="0.01" {...register(`shareholders.${i}.share_percentage`, { valueAsNumber: true })} className={inputCls(!!errors.shareholders?.[i]?.share_percentage)} />
                    </Field>
                    <Field label="Entity Type" error={errors.shareholders?.[i]?.entity_type?.message}>
                      <select {...register(`shareholders.${i}.entity_type`)} className={inputCls(false)}>
                        <option value="individual">Individual</option>
                        <option value="corporate">Corporate</option>
                      </select>
                    </Field>
                    <Field label="Nationality">
                      <input {...register(`shareholders.${i}.nationality`)} placeholder="United Kingdom" className={inputCls(false)} />
                    </Field>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => shareholders.append({ name: "", share_percentage: 10, entity_type: "individual", nationality: "" })}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-300 py-3 text-sm text-zinc-500 hover:border-teal-300 hover:text-teal-700 transition-colors"
              >
                <Plus className="h-4 w-4" /> Add Shareholder
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.push("/customer/onboarding/documents")}
          className="flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => { markStepComplete("company"); router.push("/customer/onboarding/review"); }}
            className="rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
          >
            Skip (Individual)
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-2 rounded-lg bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60 transition-colors"
          >
            {isSubmitting ? (
              <span className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
            ) : (
              <>Save & Continue <ArrowRight className="h-4 w-4" /></>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function inputCls(hasError: boolean) {
  return cn(
    "w-full rounded-lg border px-3 py-2.5 text-sm outline-none transition-all",
    hasError
      ? "border-red-300 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100"
      : "border-zinc-300 bg-white focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
  );
}

function Field({ label, error, required, children }: { label: string; error?: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {label}{required && <span className="text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
