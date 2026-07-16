import React from "react";
import Link from "next/link";
import { ShieldCheck, Zap, FileSearch, Globe, BarChart3, CheckCircle } from "lucide-react";

const features = [
  { icon: ShieldCheck, title: "AML Screening", desc: "13 AI agents running PEP, sanctions, country risk, and transaction monitoring in parallel" },
  { icon: FileSearch, title: "Document OCR", desc: "Gemini Vision extracts and validates passport, ID, and address documents automatically" },
  { icon: Globe, title: "Global Watchlists", desc: "OFAC, OFSI, UN, EU sanctions and FATF high-risk jurisdiction checks in real time" },
  { icon: BarChart3, title: "Risk Scoring", desc: "Composite risk engine combining sanctions, PEP, geography, transactions, and behaviour" },
  { icon: Zap, title: "Instant Decisions", desc: "Auto-approve low-risk profiles; escalate high-risk cases to compliance officers" },
  { icon: CheckCircle, title: "Full Audit Trail", desc: "Every agent action, decision, and data change is logged for regulatory compliance" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-zinc-950 via-teal-950 to-zinc-900 px-6 py-24 text-center text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-teal-800/30 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-3xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1.5 text-sm text-teal-300">
            <ShieldCheck className="h-3.5 w-3.5" /> UK Money Laundering Regulations 2017 Compliant
          </div>
          <h1 className="text-5xl font-extrabold leading-tight tracking-tight">
            AI-Powered{" "}
            <span className="bg-gradient-to-r from-teal-400 to-emerald-400 bg-clip-text text-transparent">
              AML & KYC
            </span>{" "}
            Compliance
          </h1>
          <p className="mt-5 text-lg text-zinc-300 leading-relaxed">
            A production-grade compliance platform combining 13 AI agents with LangGraph orchestration
            to automate customer onboarding, risk screening, and regulatory reporting.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/auth/register"
              className="rounded-xl bg-teal-500 px-8 py-3.5 font-bold text-white shadow-lg hover:bg-teal-400 transition-colors"
            >
              Start Onboarding
            </Link>
            <Link
              href="/auth/login"
              className="rounded-xl border border-zinc-700 px-8 py-3.5 font-semibold text-zinc-200 hover:border-zinc-500 hover:text-white transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-bold text-zinc-900">Everything Compliance Requires</h2>
            <p className="mt-3 text-zinc-500">Built on FastAPI, LangGraph, Gemini 2.5 Flash, and PostgreSQL</p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.title}
                  className="group rounded-xl border border-zinc-200 bg-white p-6 shadow-sm hover:border-teal-200 hover:shadow-md transition-all"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 group-hover:bg-teal-100 transition-colors">
                    <Icon className="h-5 w-5 text-teal-700" />
                  </div>
                  <h3 className="font-semibold text-zinc-900">{f.title}</h3>
                  <p className="mt-2 text-sm text-zinc-500 leading-relaxed">{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-zinc-100 bg-zinc-50 px-6 py-16 text-center">
        <div className="mx-auto max-w-xl">
          <h2 className="text-2xl font-bold text-zinc-900">Ready to begin your application?</h2>
          <p className="mt-3 text-zinc-500">Complete KYC onboarding in minutes with our guided multi-step wizard.</p>
          <Link
            href="/auth/register"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-teal-700 px-8 py-3.5 font-bold text-white shadow hover:bg-teal-800 transition-colors"
          >
            <ShieldCheck className="h-4 w-4" /> Create Account
          </Link>
        </div>
      </section>
    </div>
  );
}
