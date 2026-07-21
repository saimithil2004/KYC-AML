"use client";

import React, { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Users, ShieldAlert, Award, Activity,
  Briefcase, CheckCircle, RefreshCw, BarChart, Calendar, ShieldCheck, Cpu
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getAnalyticsKPIs, getAnalyticsCases } from "@/lib/api";
import { PeriodicKPIs } from "@/lib/types";

export default function AnalyticsDashboard() {
  const { user } = useAuth();
  const token = localStorage.getItem("token") || "";

  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly" | "quarterly" | "yearly">("monthly");
  const [loading, setLoading] = useState(false);
  const [kpis, setKpis] = useState<PeriodicKPIs | null>(null);
  const [casesAnalytics, setCasesAnalytics] = useState<any>(null);
  const [errMessage, setErrMessage] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setErrMessage("");
    try {
      const res = await getAnalyticsKPIs(token, period);
      setKpis(res);

      const casesRes = await getAnalyticsCases(token);
      setCasesAnalytics(casesRes);
    } catch (err: any) {
      console.error(err);
      setErrMessage("Failed to retrieve Executive BI Analytics payload.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [period]);

  // SVG Chart helpers
  const riskCategories = kpis?.distributions.risk_category || {};
  const riskData = [
    { label: "Critical", value: riskCategories.critical || 0, color: "bg-rose-600" },
    { label: "High", value: riskCategories.high || 0, color: "bg-rose-500" },
    { label: "Medium", value: riskCategories.medium || 0, color: "bg-amber-500" },
    { label: "Low", value: riskCategories.low || 0, color: "bg-teal-500" }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-black text-zinc-950 dark:text-white flex items-center gap-2">
            <TrendingUp className="text-teal-600 h-6 w-6" /> Executive Business Intelligence
          </h1>
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-400">
            Real-time operations throughput, AI agent performance charts, and risk aggregates
          </p>
        </div>

        {/* Period filter & Refresh */}
        <div className="flex items-center gap-2">
          <div className="flex bg-zinc-100 rounded-lg p-1 border border-zinc-200">
            {(["daily", "weekly", "monthly", "quarterly", "yearly"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 text-xs font-bold rounded-md transition capitalize ${
                  period === p
                    ? "bg-white text-zinc-950 shadow-sm"
                    : "text-zinc-500 hover:text-zinc-900"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1 px-3 py-2 rounded-lg border border-zinc-200 bg-white text-xs font-bold text-zinc-700 hover:bg-zinc-50 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Sync
          </button>
        </div>
      </div>

      {errMessage && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-100 text-rose-800 text-sm font-semibold">
          {errMessage}
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-2">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Customer Growth</span>
            <Users className="h-5 w-5 text-teal-600" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">+{kpis?.metrics.new_customers ?? 0}</p>
          <p className="text-xs text-zinc-500">Onboarded in period · Total {kpis?.metrics.total_customers}</p>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-2">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">KYC Completion Rate</span>
            <ShieldCheck className="h-5 w-5 text-indigo-500" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{kpis?.metrics.kyc_completion_rate ?? 0}%</p>
          <p className="text-xs text-zinc-500">Approved customer profiles</p>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-2">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Avg Risk Score</span>
            <ShieldAlert className="h-5 w-5 text-amber-500" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{kpis?.metrics.average_risk_score ?? 0}</p>
          <p className="text-xs text-zinc-500">Average risk baseline score</p>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-2">
          <div className="flex justify-between items-center text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">AI Success Rate</span>
            <Cpu className="h-5 w-5 text-purple-600" />
          </div>
          <p className="text-3xl font-extrabold text-zinc-900">{kpis?.metrics.agent_success_rate ?? 0}%</p>
          <p className="text-xs text-zinc-500">{kpis?.metrics.agent_executions ?? 0} agent executions</p>
        </div>
      </div>

      {/* Main Charts & Distribution Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Risk Distribution Visuals */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
            <BarChart className="h-4.5 w-4.5 text-zinc-500" />
            Risk Distribution
          </h3>
          <div className="space-y-4.5">
            {riskData.map((tier) => {
              const maxVal = Math.max(...riskData.map((d) => d.value), 1);
              const pct = (tier.value / maxVal) * 100;
              return (
                <div key={tier.label} className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-zinc-800">{tier.label}</span>
                    <span className="text-zinc-500">{tier.value} customers</span>
                  </div>
                  <div className="h-2.5 w-full bg-zinc-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${tier.color}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top Alert Types list */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
            <Award className="h-4.5 w-4.5 text-zinc-500" />
            Top Alert Categories
          </h3>
          <div className="space-y-3.5">
            {kpis?.distributions.top_alerts.map((al) => (
              <div key={al.type} className="flex justify-between items-center text-xs border-b border-zinc-100 pb-2.5 last:border-0 last:pb-0">
                <span className="font-bold text-zinc-800 uppercase tracking-wide">{al.type.replace(/_/g, " ")}</span>
                <span className="rounded bg-rose-50 text-rose-700 font-bold px-2 py-0.5 border border-rose-100">{al.count} counts</span>
              </div>
            ))}
            {(!kpis?.distributions.top_alerts || kpis.distributions.top_alerts.length === 0) && (
              <p className="text-xs text-zinc-400 text-center py-6">No alerts triggered in this period.</p>
            )}
          </div>
        </div>

        {/* Top Onboarded Nationality Map */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
            <Activity className="h-4.5 w-4.5 text-zinc-500" />
            Top Countries Risk Footprint
          </h3>
          <div className="space-y-3.5">
            {kpis?.distributions.country_distribution.map((c) => (
              <div key={c.country} className="flex justify-between items-center text-xs border-b border-zinc-100 pb-2.5 last:border-0 last:pb-0">
                <span className="font-bold text-zinc-800">{c.country}</span>
                <span className="rounded bg-zinc-100 text-zinc-700 font-semibold px-2 py-0.5">{c.count} clients</span>
              </div>
            ))}
            {(!kpis?.distributions.country_distribution || kpis.distributions.country_distribution.length === 0) && (
              <p className="text-xs text-zinc-400 text-center py-6">No country distribution details.</p>
            )}
          </div>
        </div>

      </div>

      {/* Case Analytics & Investigator balancing */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Case analytics overview */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
            <Briefcase className="h-4.5 w-4.5 text-zinc-500" />
            Operational Case Status Breakdown
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-zinc-50 p-4 text-center border border-zinc-150">
              <p className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider">Open Cases</p>
              <p className="text-3xl font-black text-indigo-600 mt-1">{casesAnalytics?.open_cases ?? 0}</p>
            </div>
            <div className="rounded-lg bg-zinc-50 p-4 text-center border border-zinc-150">
              <p className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider">Resolved Cases</p>
              <p className="text-3xl font-black text-teal-600 mt-1">{casesAnalytics?.closed_cases ?? 0}</p>
            </div>
          </div>
        </div>

        {/* Leaderboard investigators */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
            <CheckCircle className="h-4.5 w-4.5 text-zinc-500" />
            Top Investigator Performance (Closed Cases count)
          </h3>
          <div className="space-y-3">
            {casesAnalytics?.investigators_leaderboard.map((inv: any, idx: number) => (
              <div key={inv.email} className="flex justify-between items-center text-xs pb-2 border-b border-zinc-100 last:border-0 last:pb-0">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-zinc-400">#{idx + 1}</span>
                  <span className="font-medium text-zinc-800">{inv.email}</span>
                </div>
                <span className="font-black text-teal-600">{inv.resolved_cases} resolved</span>
              </div>
            ))}
            {(!casesAnalytics?.investigators_leaderboard || casesAnalytics.investigators_leaderboard.length === 0) && (
              <p className="text-xs text-zinc-400 text-center py-6">No closed case leaderboards.</p>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
