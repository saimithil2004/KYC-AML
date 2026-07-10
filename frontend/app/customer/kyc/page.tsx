"use client";

import React, { useEffect, useState } from "react";
import { ProtectedRoute } from "../../../components/ProtectedRoute";
import { buttonClass, FormField, inputClass } from "../../../components/FormField";
import { useAuth } from "../../../context/AuthContext";
import { apiRequest, ensureCustomer, KycProfile } from "../../../lib/api";

const emptyForm = {
  full_name: "",
  dob: "",
  nationality: "",
  address: "",
  occupation: "",
  source_of_funds: "",
  source_of_wealth: "",
  risk_category: "low",
};

export default function KycFormPage() {
  const { token } = useAuth();
  const [customerId, setCustomerId] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [hasProfile, setHasProfile] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    const load = async () => {
      if (!token) return;
      const customer = await ensureCustomer(token);
      setCustomerId(customer.id);
      try {
        const profile = await apiRequest<KycProfile>(`/kyc/${customer.id}`, {}, token);
        setHasProfile(true);
        setForm({
          full_name: profile.full_name,
          dob: profile.dob,
          nationality: profile.nationality,
          address: profile.address,
          occupation: profile.occupation,
          source_of_funds: profile.source_of_funds,
          source_of_wealth: profile.source_of_wealth,
          risk_category: profile.risk_category,
        });
      } catch {
        setHasProfile(false);
      }
    };
    load().catch(console.error);
  }, [token]);

  const update = (field: keyof typeof emptyForm, value: string) => setForm((current) => ({ ...current, [field]: value }));

  const submitKyc = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token || !customerId) return;
    setStatusMsg("Submitting KYC profile...");
    try {
      await apiRequest<KycProfile>(
        hasProfile ? `/kyc/${customerId}` : "/kyc/",
        { method: hasProfile ? "PUT" : "POST", body: JSON.stringify({ ...form, customer_id: customerId }) },
        token,
      );
      setHasProfile(true);
      setStatusMsg("KYC profile saved.");
    } catch (error) {
      setStatusMsg(error instanceof Error ? error.message : "KYC submission failed.");
    }
  };

  return (
    <ProtectedRoute>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-zinc-950">KYC Form</h1>
          <p className="text-zinc-600">Submit source of funds, wealth, occupation, and risk declarations.</p>
        </div>
        <form onSubmit={submitKyc} className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="Full Name"><input required className={inputClass} value={form.full_name} onChange={(event) => update("full_name", event.target.value)} /></FormField>
            <FormField label="Date Of Birth"><input required type="date" className={inputClass} value={form.dob} onChange={(event) => update("dob", event.target.value)} /></FormField>
            <FormField label="Nationality"><input required className={inputClass} value={form.nationality} onChange={(event) => update("nationality", event.target.value)} /></FormField>
            <FormField label="Occupation"><input required className={inputClass} value={form.occupation} onChange={(event) => update("occupation", event.target.value)} /></FormField>
            <FormField label="Source Of Funds">
              <select required className={inputClass} value={form.source_of_funds} onChange={(event) => update("source_of_funds", event.target.value)}>
                <option value="">Select source</option>
                <option value="Salary">Salary</option>
                <option value="Business Income">Business Income</option>
                <option value="Savings">Savings</option>
                <option value="Inheritance">Inheritance</option>
                <option value="Investment Returns">Investment Returns</option>
              </select>
            </FormField>
            <FormField label="Risk Category">
              <select className={inputClass} value={form.risk_category} onChange={(event) => update("risk_category", event.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </FormField>
          </div>
          <div className="mt-4 space-y-4">
            <FormField label="Address"><textarea required className={`${inputClass} min-h-20`} value={form.address} onChange={(event) => update("address", event.target.value)} /></FormField>
            <FormField label="Source Of Wealth"><textarea required className={`${inputClass} min-h-24`} value={form.source_of_wealth} onChange={(event) => update("source_of_wealth", event.target.value)} /></FormField>
          </div>
          <button className={`${buttonClass} mt-5`} type="submit">{hasProfile ? "Update KYC" : "Submit KYC"}</button>
          {statusMsg && <p className="mt-4 text-sm text-teal-700">{statusMsg}</p>}
        </form>
      </div>
    </ProtectedRoute>
  );
}
