"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ProtectedRoute } from "../../../components/ProtectedRoute";
import { useAuth } from "../../../context/AuthContext";
import { apiRequest, Customer, ensureCustomer, KycProfile } from "../../../lib/api";

export default function CustomerDashboard() {
  const { token } = useAuth();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [kyc, setKyc] = useState<KycProfile | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!token) return;
      const currentCustomer = await ensureCustomer(token);
      setCustomer(currentCustomer);
      try {
        setKyc(await apiRequest<KycProfile>(`/kyc/${currentCustomer.id}`, {}, token));
      } catch {
        setKyc(null);
      }
    };
    load().catch(console.error);
  }, [token]);

  return (
    <ProtectedRoute>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-zinc-950">Customer Dashboard</h1>
          <p className="text-zinc-600">Compliance onboarding status and next actions.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Customer Status</p>
            <p className="mt-3 text-2xl font-bold capitalize text-zinc-950">{customer?.status?.replaceAll("_", " ") || "Loading"}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">KYC Risk</p>
            <p className="mt-3 text-2xl font-bold capitalize text-teal-800">{kyc?.risk_category || "Not submitted"}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Profile Type</p>
            <p className="mt-3 text-2xl font-bold capitalize text-zinc-950">{customer?.customer_type || "Individual"}</p>
          </div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-zinc-950">Onboarding Actions</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Link href="/customer/profile" className="rounded-md border border-zinc-200 p-4 text-sm font-medium text-zinc-700 hover:border-teal-300 hover:bg-teal-50">Update profile</Link>
            <Link href="/customer/kyc" className="rounded-md border border-zinc-200 p-4 text-sm font-medium text-zinc-700 hover:border-teal-300 hover:bg-teal-50">Submit KYC</Link>
            <Link href="/customer/documents" className="rounded-md border border-zinc-200 p-4 text-sm font-medium text-zinc-700 hover:border-teal-300 hover:bg-teal-50">Upload documents</Link>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
