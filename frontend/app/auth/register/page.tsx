"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { buttonClass, FormField, inputClass } from "../../../components/FormField";
import { useAuth } from "../../../context/AuthContext";

export default function RegisterPage() {
  const { register, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("customer");
  const [statusMsg, setStatusMsg] = useState("");
  const router = useRouter();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatusMsg("Registering account...");
    try {
      await register(email, password, role);
      setStatusMsg("Registration successful. Redirecting to login...");
      setTimeout(() => router.push("/auth/login"), 1000);
    } catch {
      setStatusMsg("");
    }
  };

  return (
    <div className="mx-auto mt-12 max-w-md rounded-lg border border-zinc-200 bg-white p-8 shadow-sm">
      <h2 className="mb-6 text-center text-2xl font-bold text-zinc-950">Create Compliance Profile</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label="Email Address">
          <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className={inputClass} placeholder="name@institution.com" />
        </FormField>
        <FormField label="Create Password">
          <input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} placeholder="Minimum 8 characters" />
        </FormField>
        <FormField label="Account Role">
          <select value={role} onChange={(event) => setRole(event.target.value)} className={inputClass}>
            <option value="customer">Customer</option>
            <option value="compliance_officer">Compliance Officer</option>
            <option value="admin">Admin</option>
          </select>
        </FormField>
        <button type="submit" className={`${buttonClass} mt-4 w-full`}>
          Submit Registration
        </button>
      </form>
      {statusMsg && <p className="mt-4 text-center text-sm text-teal-700">{statusMsg}</p>}
      {error && <p className="mt-4 text-center text-sm text-red-600">{error}</p>}
      <p className="mt-6 text-center text-xs text-zinc-500">
        Already have an account? <Link href="/auth/login" className="text-teal-700 hover:underline">Sign in here</Link>
      </p>
    </div>
  );
}
