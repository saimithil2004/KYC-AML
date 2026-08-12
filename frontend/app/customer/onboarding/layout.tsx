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
      <div className="mx-auto max-w-4xl space-y-6 animate-fade-in">
        {/* Step Indicator */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-1">
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
                          ? "border-teal-600 bg-teal-600 text-white"
                          : active
                          ? "border-teal-600 bg-white text-teal-700 shadow-md animate-pulse-glow"
                          : accessible
                          ? "border-zinc-300 bg-white text-zinc-500 hover:border-zinc-400"
                          : "border-zinc-200 bg-zinc-50 text-zinc-300"
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
                        "hidden text-[10px] font-medium sm:block",
                        active ? "text-teal-700" : done ? "text-teal-600" : "text-zinc-400"
                      )}
                    >
                      {step.label}
                    </span>
                  </div>

                  {i < STEPS.length - 1 && (
                    <div
                      className={cn(
                        "h-0.5 flex-1 rounded-full transition-all duration-500",
                        done ? "bg-teal-500" : "bg-zinc-200"
                      )}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {draft.lastSaved && (
            <p className="mt-3 text-center text-[11px] text-zinc-400">
              Draft auto-saved{" "}
              {new Date(draft.lastSaved).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>

        {/* Page Content */}
        {children}
      </div>
    </ProtectedRoute>
  );
}
