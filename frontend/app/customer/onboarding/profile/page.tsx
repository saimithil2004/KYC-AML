"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { UserRound, ArrowRight, Save } from "lucide-react";
import { profileSchema, type ProfileFormData, CUSTOMER_TYPES } from "@/lib/types";
import { useCustomer } from "@/hooks/usePortalData";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { cn } from "@/lib/utils";

const COUNTRIES = [
  "United Kingdom", "United States", "Canada", "Australia", "Germany",
  "France", "Spain", "Italy", "Netherlands", "Sweden", "Norway", "Denmark",
  "India", "Singapore", "UAE", "South Africa", "Nigeria", "Ghana",
  "Other",
];

export default function ProfileStep() {
  const router = useRouter();
  const { data: customer, isLoading, update } = useCustomer();
  const { draft, save: saveDraft, markStepComplete, setCustomerType } = useOnboardingDraft();

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      customer_type: "individual",
      first_name: "",
      last_name: "",
      dob: "",
      nationality: "",
      phone_number: "",
      street_address: "",
      city: "",
      postal_code: "",
      country: "",
    },
  });

  // Populate form when customer data loads
  useEffect(() => {
    if (customer) {
      reset({
        customer_type: customer.customer_type || "individual",
        first_name: customer.first_name || "",
        last_name: customer.last_name || "",
        dob: customer.dob || "",
        nationality: customer.nationality || "",
        phone_number: customer.phone_number || "",
        street_address: customer.street_address || "",
        city: customer.city || "",
        postal_code: customer.postal_code || "",
        country: customer.country || "",
      });
    }
  }, [customer, reset]);

  const customerType = watch("customer_type");

  const onSubmit = async (data: ProfileFormData) => {
    try {
      await update.mutateAsync({
        customer_type: data.customer_type,
        first_name: data.first_name,
        last_name: data.last_name,
        dob: data.dob,
        nationality: data.nationality,
        phone_number: data.phone_number,
        street_address: data.street_address,
        city: data.city,
        postal_code: data.postal_code,
        country: data.country,
      });

      setCustomerType(data.customer_type);
      markStepComplete("profile");
      saveDraft({ profileComplete: true });
      toast.success("Profile saved successfully");
      router.push("/customer/onboarding/kyc");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save profile");
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
          <UserRound className="h-5 w-5 text-teal-700" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Customer Profile</h1>
          <p className="text-sm text-zinc-500">
            Step 1 of 5 — Personal details used for identity verification
          </p>
        </div>
        {draft.profileComplete && (
          <span className="ml-auto flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 border border-emerald-200">
            <Save className="h-3 w-3" /> Saved
          </span>
        )}
      </div>

      {/* Customer Type */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-zinc-700">Customer Type</h2>
        <div className="grid grid-cols-2 gap-3">
          {CUSTOMER_TYPES.map((type) => (
            <label
              key={type}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 p-4 transition-all",
                customerType === type
                  ? "border-teal-600 bg-teal-50 shadow-sm"
                  : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50"
              )}
            >
              <input
                type="radio"
                value={type}
                {...register("customer_type")}
                className="sr-only"
              />
              <span className="text-2xl">{type === "individual" ? "👤" : "🏢"}</span>
              <span className="text-sm font-semibold capitalize text-zinc-800">{type}</span>
              <span className="text-center text-[11px] text-zinc-500">
                {type === "individual"
                  ? "Personal account for individuals"
                  : "Business or corporate entity"}
              </span>
            </label>
          ))}
        </div>
        {errors.customer_type && (
          <p className="mt-2 text-xs text-red-600">{errors.customer_type.message}</p>
        )}
      </div>

      {/* Personal Details */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-zinc-700">Personal Details</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First Name" error={errors.first_name?.message} required>
            <input {...register("first_name")} placeholder="John" className={inputCls(!!errors.first_name)} />
          </Field>
          <Field label="Last Name" error={errors.last_name?.message} required>
            <input {...register("last_name")} placeholder="Smith" className={inputCls(!!errors.last_name)} />
          </Field>
          <Field label="Date of Birth" error={errors.dob?.message} required>
            <input type="date" {...register("dob")} className={inputCls(!!errors.dob)} />
          </Field>
          <Field label="Nationality" error={errors.nationality?.message} required>
            <select {...register("nationality")} className={inputCls(!!errors.nationality)}>
              <option value="">Select nationality</option>
              {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Phone Number" error={errors.phone_number?.message} required>
            <input {...register("phone_number")} placeholder="+44 7700 900000" className={inputCls(!!errors.phone_number)} />
          </Field>
        </div>
      </div>

      {/* Address */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-zinc-700">Residential Address</h2>
        <div className="space-y-4">
          <Field label="Street Address" error={errors.street_address?.message} required>
            <input {...register("street_address")} placeholder="123 Baker Street" className={inputCls(!!errors.street_address)} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="City" error={errors.city?.message} required>
              <input {...register("city")} placeholder="London" className={inputCls(!!errors.city)} />
            </Field>
            <Field label="Postal Code" error={errors.postal_code?.message} required>
              <input {...register("postal_code")} placeholder="W1A 1AA" className={inputCls(!!errors.postal_code)} />
            </Field>
            <Field label="Country" error={errors.country?.message} required>
              <select {...register("country")} className={inputCls(!!errors.country)}>
                <option value="">Select country</option>
                {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-zinc-400">Changes are saved when you continue</p>
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex items-center gap-2 rounded-lg bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60 transition-colors"
        >
          {isSubmitting ? (
            <span className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
          ) : (
            <>Continue to KYC <ArrowRight className="h-4 w-4" /></>
          )}
        </button>
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

function Field({
  label,
  error,
  required,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {label}
        {required && <span className="text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
