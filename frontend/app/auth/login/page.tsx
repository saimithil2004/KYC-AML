"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { buttonClass, FormField, inputClass } from "../../../components/FormField";
import { useAuth } from "../../../context/AuthContext";

export default function LoginPage() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const router = useRouter();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatusMsg("Authenticating credentials...");
    try {
      await login(email, password);
      router.push("/customer/dashboard");
    } catch {
      setStatusMsg("");
    }
  };

  return (
    <div className="mx-auto mt-12 max-w-md rounded-lg border border-zinc-200 bg-white p-8 shadow-sm">
      <h2 className="mb-6 text-center text-2xl font-bold text-zinc-950">Client Portal Access</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label="Email Address">
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={inputClass}
            placeholder="name@institution.com"
          />
        </FormField>
        <FormField label="Secure Password">
          <input
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={inputClass}
            placeholder="Minimum 8 characters"
          />
        </FormField>
        <button type="submit" className={`${buttonClass} mt-4 w-full`}>
          Sign In
        </button>
      </form>
      {statusMsg && <p className="mt-4 text-center text-sm text-teal-700">{statusMsg}</p>}
      {error && <p className="mt-4 text-center text-sm text-red-600">{error}</p>}
      <p className="mt-6 text-center text-xs text-zinc-500">
        Do not have an account? <Link href="/auth/register" className="text-teal-700 hover:underline">Register here</Link>
      </p>
    </div>
  );
}
