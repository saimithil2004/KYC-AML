"use client";

import { useCallback, useEffect, useState } from "react";
import type { OnboardingDraft, OnboardingStep } from "@/lib/types";

const DRAFT_KEY = "kyc_onboarding_draft";

const defaultDraft: OnboardingDraft = {
  profileComplete: false,
  kycComplete: false,
  documentsComplete: false,
  companyComplete: false,
  currentStep: "profile",
};

export function useOnboardingDraft() {
  const [draft, setDraft] = useState<OnboardingDraft>(defaultDraft);
  const [hydrated, setHydrated] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) {
        setDraft(JSON.parse(saved) as OnboardingDraft);
      }
    } catch {
      // ignore
    }
    setHydrated(true);
  }, []);

  const save = useCallback((updates: Partial<OnboardingDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...updates, lastSaved: new Date().toISOString() };
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const markStepComplete = useCallback(
    (step: OnboardingStep) => {
      const stepMap: Record<OnboardingStep, keyof OnboardingDraft> = {
        profile: "profileComplete",
        kyc: "kycComplete",
        documents: "documentsComplete",
        company: "companyComplete",
        review: "profileComplete", // review doesn't have its own flag
        submitted: "profileComplete",
      };
      const field = stepMap[step];
      if (field) save({ [field]: true } as Partial<OnboardingDraft>);
    },
    [save]
  );

  const setCurrentStep = useCallback(
    (step: OnboardingStep) => save({ currentStep: step }),
    [save]
  );

  const setCustomerId = useCallback(
    (customerId: string) => save({ customerId }),
    [save]
  );

  const setCustomerType = useCallback(
    (customerType: "individual" | "corporate") => save({ customerType }),
    [save]
  );

  const clearDraft = useCallback(() => {
    localStorage.removeItem(DRAFT_KEY);
    setDraft(defaultDraft);
  }, []);

  const completionPercent = Math.round(
    ([
      draft.profileComplete,
      draft.kycComplete,
      draft.documentsComplete,
      draft.customerType === "corporate" ? draft.companyComplete : true,
    ].filter(Boolean).length /
      (draft.customerType === "corporate" ? 4 : 3)) *
      100
  );

  return {
    draft,
    hydrated,
    save,
    markStepComplete,
    setCurrentStep,
    setCustomerId,
    setCustomerType,
    clearDraft,
    completionPercent,
  };
}
