"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import {
  ensureCustomer,
  updateCustomer,
  getKycProfile,
  createKycProfile,
  updateKycProfile,
  getCustomerDocuments,
  apiRequest,
} from "@/lib/api";
import type { Customer, KycProfile, DocumentRecord } from "@/lib/types";

// ─── useCustomer ─────────────────────────────────────────────────────────────
export function useCustomer() {
  const { token } = useAuth();
  const qc = useQueryClient();

  const query = useQuery<Customer>({
    queryKey: ["customer"],
    queryFn: () => ensureCustomer(token!),
    enabled: !!token,
  });

  const mutation = useMutation({
    mutationFn: (data: Partial<Customer>) =>
      updateCustomer(query.data!.id, data, token!),
    onSuccess: (updated) => {
      qc.setQueryData(["customer"], updated);
    },
  });

  return { ...query, update: mutation };
}

// ─── useKycProfile ───────────────────────────────────────────────────────────
export function useKycProfile(customerId?: string) {
  const { token } = useAuth();
  const qc = useQueryClient();

  const query = useQuery<KycProfile | null>({
    queryKey: ["kycProfile", customerId],
    queryFn: async () => {
      try {
        return await getKycProfile(customerId!, token!);
      } catch {
        return null;
      }
    },
    enabled: !!token && !!customerId,
  });

  const create = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createKycProfile(data, token!),
    onSuccess: (created) => {
      qc.setQueryData(["kycProfile", customerId], created);
    },
  });

  const update = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      updateKycProfile(customerId!, data, token!),
    onSuccess: (updated) => {
      qc.setQueryData(["kycProfile", customerId], updated);
    },
  });

  return { ...query, create, update, hasProfile: !!query.data };
}

// ─── useDocuments ─────────────────────────────────────────────────────────────
export function useDocuments(customerId?: string) {
  const { token } = useAuth();
  const qc = useQueryClient();

  const query = useQuery<DocumentRecord[]>({
    queryKey: ["documents", customerId],
    queryFn: () => getCustomerDocuments(customerId!, token!),
    enabled: !!token && !!customerId,
    initialData: [],
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["documents", customerId] });

  return { ...query, invalidate };
}

// ─── useCompany ──────────────────────────────────────────────────────────────
export function useCompany() {
  const { token } = useAuth();
  const query = useQuery({
    queryKey: ["company"],
    queryFn: async () => {
      try {
        return await apiRequest<{
          company: any;
          directors: any[];
          ubos: any[];
        }>("/customers/me/company", {}, token!);
      } catch {
        return null;
      }
    },
    enabled: !!token,
  });
  return query;
}
