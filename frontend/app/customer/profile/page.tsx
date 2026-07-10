"use client";

import React, { useEffect, useState } from "react";
import { ProtectedRoute } from "../../../components/ProtectedRoute";
import { buttonClass, FormField, inputClass } from "../../../components/FormField";
import { useAuth } from "../../../context/AuthContext";
import { apiRequest, Customer, ensureCustomer } from "../../../lib/api";

export default function CustomerProfilePage() {
  const { token } = useAuth();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    if (!token) return;
    ensureCustomer(token).then(setCustomer).catch(console.error);
  }, [token]);

  const updateField = (field: keyof Customer, value: string) => {
    setCustomer((current) => (current ? { ...current, [field]: value } : current));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token || !customer) return;
    setStatusMsg("Saving customer profile...");
    try {
      const updated = await apiRequest<Customer>(
        `/customers/${customer.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            customer_type: customer.customer_type,
            first_name: customer.first_name,
            last_name: customer.last_name,
            dob: customer.dob,
            nationality: customer.nationality,
            phone_number: customer.phone_number,
            street_address: customer.street_address,
            city: customer.city,
            postal_code: customer.postal_code,
            country: customer.country,
          }),
        },
        token,
      );
      setCustomer(updated);
      setStatusMsg("Customer profile saved.");
    } catch (error) {
      setStatusMsg(error instanceof Error ? error.message : "Profile update failed.");
    }
  };

  return (
    <ProtectedRoute>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-zinc-950">Customer Profile</h1>
          <p className="text-zinc-600">Maintain onboarding details used for KYC screening.</p>
        </div>
        <form onSubmit={handleSubmit} className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="First Name"><input className={inputClass} value={customer?.first_name || ""} onChange={(event) => updateField("first_name", event.target.value)} /></FormField>
            <FormField label="Last Name"><input className={inputClass} value={customer?.last_name || ""} onChange={(event) => updateField("last_name", event.target.value)} /></FormField>
            <FormField label="Date Of Birth"><input type="date" className={inputClass} value={customer?.dob || ""} onChange={(event) => updateField("dob", event.target.value)} /></FormField>
            <FormField label="Nationality"><input className={inputClass} value={customer?.nationality || ""} onChange={(event) => updateField("nationality", event.target.value)} /></FormField>
            <FormField label="Phone Number"><input className={inputClass} value={customer?.phone_number || ""} onChange={(event) => updateField("phone_number", event.target.value)} /></FormField>
            <FormField label="Country"><input className={inputClass} value={customer?.country || ""} onChange={(event) => updateField("country", event.target.value)} /></FormField>
            <FormField label="City"><input className={inputClass} value={customer?.city || ""} onChange={(event) => updateField("city", event.target.value)} /></FormField>
            <FormField label="Postal Code"><input className={inputClass} value={customer?.postal_code || ""} onChange={(event) => updateField("postal_code", event.target.value)} /></FormField>
          </div>
          <div className="mt-4">
            <FormField label="Street Address"><textarea className={`${inputClass} min-h-24`} value={customer?.street_address || ""} onChange={(event) => updateField("street_address", event.target.value)} /></FormField>
          </div>
          <button className={`${buttonClass} mt-5`} type="submit">Save Profile</button>
          {statusMsg && <p className="mt-4 text-sm text-teal-700">{statusMsg}</p>}
        </form>
      </div>
    </ProtectedRoute>
  );
}
