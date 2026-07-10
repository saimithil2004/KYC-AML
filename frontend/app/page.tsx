import React from "react";
import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="mx-auto mt-16 max-w-3xl">
      <div className="rounded-lg border border-zinc-200 bg-white p-8 shadow-sm">
        <h1 className="text-4xl font-bold tracking-tight text-zinc-950">AML + KYC Compliance Portal</h1>
        <p className="mt-4 text-base text-zinc-600">
          Register, complete customer onboarding, submit KYC declarations, and upload verification documents.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/auth/login" className="rounded-md bg-teal-700 px-5 py-3 text-sm font-semibold text-white hover:bg-teal-800">
            Access Portal
          </Link>
          <Link href="/auth/register" className="rounded-md border border-zinc-300 px-5 py-3 text-sm font-semibold text-zinc-700 hover:bg-zinc-50">
            Register Account
          </Link>
        </div>
      </div>
    </div>
  );
}
