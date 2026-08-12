"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Check, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useOnboardingDraft } from "@/hooks/useOnboardingDraft";
import { useCustomer, useKycProfile, useDocuments } from "@/hooks/usePortalData";

const STEPS = [
  { key: "profile",   label: "Profile",   path: "/customer/onboarding/profile"   },
  { key: "kyc",       label: "KYC",       path: "/customer/onboarding/kyc"       },
  { key: "documents", label: "Documents", path: "/customer/onboarding/documents" },
  { key: "company",   label: "Company",   path: "/customer/onboarding/company"   },
  { key: "review",    label: "Review",    path: "/customer/onboarding/review"    },
];

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: customer } = useCustomer();
  const { data: kyc } = useKycProfile(customer?.id);
  const { data: documents } = useDocuments(customer?.id);
  const { draft } = useOnboardingDraft();

  const currentIndex = STEPS.findIndex((s) => pathname?.startsWith(s.path));

  const isSubmittedOrProcessed = Boolean(
    customer?.status && customer.status !== "onboarding"
  );

  const isStepDone = (key: string): boolean => {
    if (isSubmittedOrProcessed) return true;
    const map: Record<string, boolean> = {
      profile:   draft.profileComplete || Boolean(customer?.first_name),
      kyc:       draft.kycComplete || Boolean(kyc?.full_name),
      documents: draft.documentsComplete || ((documents?.length ?? 0) > 0),
      company:   draft.companyComplete || customer?.customer_type !== "corporate",
    };
    return map[key] ?? false;
  };

  const isStepAccessible = (index: number): boolean => {
    if (index === 0 || isSubmittedOrProcessed) return true;
    const prev = STEPS[index - 1];
    return isStepDone(prev.key);
  };

  return (
    <ProtectedRoute>
      <div className="mx-auto max-w-4xl space-y-6 animate-fade-in text-zinc-100">
        {/* Step Indicator Card */}
        <div className="glass-card rounded-2xl border border-zinc-800/80 p-5 backdrop-blur-xl shadow-2xl">
          <div className="flex items-center gap-1.5">
            {STEPS.map((step, i) => {
              const done = isStepDone(step.key);
              const active = i === currentIndex;
              const accessible = isStepAccessible(i);

              return (
                <React.Fragment key={step.key}>
                  <div className="flex flex-1 flex-col items-center gap-1.5">
                    <div
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold border-2 transition-all duration-300",
                        done
                          ? "border-teal-500 bg-teal-500 text-white shadow-[0_0_15px_rgba(20,184,166,0.5)]"
                          : active
                          ? "border-teal-400 bg-zinc-900 text-teal-300 shadow-[0_0_20px_rgba(20,184,166,0.4)] animate-pulse-glow"
                          : accessible
                          ? "border-zinc-700 bg-zinc-900/80 text-zinc-400 hover:border-zinc-500"
                          : "border-zinc-800 bg-zinc-950 text-zinc-600"
                      )}
                    >
                      {done ? (
                        <Check className="h-4 w-4" />
                      ) : !accessible ? (
                        <Lock className="h-3.5 w-3.5" />
                      ) : (
                        i + 1
                      )}
                    </div>
                    <span
                      className={cn(
                        "hidden text-[11px] font-semibold tracking-wide uppercase sm:block",
                        active ? "text-teal-300" : done ? "text-teal-400" : "text-zinc-500"
                      )}
                    >
                      {step.label}
                    </span>
                  </div>

                  {i < STEPS.length - 1 && (
                    <div
                      className={cn(
                        "h-0.5 flex-1 rounded-full transition-all duration-500",
                        done ? "bg-gradient-to-r from-teal-500 to-emerald-400 shadow-[0_0_10px_rgba(20,184,166,0.5)]" : "bg-zinc-800"
                      )}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Content Box */}
        <div className="glass-card rounded-2xl border border-zinc-800/80 p-8 backdrop-blur-xl shadow-2xl">
          {children}
        </div>
      </div>
    </ProtectedRoute>
  );
}
