"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { getAIDashboardMetrics, getAIUsageStats, getAIProviderStatus } from "@/lib/api";
import type { AIStatistics, AIUsage } from "@/lib/types";
import {
  Brain, Cpu, Zap, Coins, Clock, CheckCircle2, AlertTriangle, ShieldCheck,
  RefreshCw, TrendingUp, BarChart3, Activity
} from "lucide-react";

export default function AIDashboardPage() {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState<AIStatistics | null>(null);
  const [usage, setUsage] = useState<AIUsage[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setErrorMsg("");
      const [mRes, uRes, pRes] = await Promise.all([
        getAIDashboardMetrics(token),
        getAIUsageStats(token),
        getAIProviderStatus(token)
      ]);
      setMetrics(mRes);
      setUsage(uRes.results || []);
      setProviders(pRes.providers || []);
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to load AI governance metrics.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-teal-600" />
        <span className="ml-3 text-sm text-zinc-600 font-semibold">Loading AI Governance stats...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white p-6 rounded-2xl shadow-sm border border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
            <Brain className="h-6 w-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">AI Governance & Analytics</h1>
            <p className="text-xs text-zinc-400">LLM registry, token consumption metrics, price estimation, and human-in-the-loop audit logs</p>
          </div>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-750 text-xs font-semibold rounded-lg transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Reload Stats
        </button>
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
          <AlertTriangle className="h-4.5 w-4.5 text-rose-500 shrink-0" />
          <p className="font-semibold">{errorMsg}</p>
        </div>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
          <div className="flex justify-between items-start text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Total Executions</span>
            <Cpu className="h-4 w-4 text-zinc-400" />
          </div>
          <p className="text-2xl font-bold text-zinc-800 mt-2">{metrics?.total_executions}</p>
          <div className="flex items-center gap-1 mt-1 text-[10px] text-zinc-400">
            <TrendingUp className="h-3 w-3 text-emerald-600" />
            <span>Active model execution runs</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
          <div className="flex justify-between items-start text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Accumulated Cost</span>
            <Coins className="h-4 w-4 text-zinc-400" />
          </div>
          <p className="text-2xl font-bold text-zinc-800 mt-2">${metrics?.total_cost_usd?.toFixed(4)}</p>
          <div className="flex items-center gap-1 mt-1 text-[10px] text-zinc-400">
            <span>Estimated LLM provider usage cost</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
          <div className="flex justify-between items-start text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Average Latency</span>
            <Clock className="h-4 w-4 text-zinc-400" />
          </div>
          <p className="text-2xl font-bold text-zinc-800 mt-2">{metrics?.average_latency_ms?.toFixed(0)} ms</p>
          <div className="flex items-center gap-1 mt-1 text-[10px] text-zinc-400">
            <span>Average API response duration</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
          <div className="flex justify-between items-start text-zinc-400">
            <span className="text-[10px] font-bold uppercase tracking-wider">Avg Confidence</span>
            <ShieldCheck className="h-4 w-4 text-zinc-400" />
          </div>
          <p className="text-2xl font-bold text-zinc-800 mt-2">{metrics?.average_confidence?.toFixed(1)}%</p>
          <div className="flex items-center gap-1 mt-1 text-[10px] text-emerald-600 font-bold">
            <span>Compliance target met</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily Stats Table */}
        <div className="bg-white p-6 rounded-xl border border-zinc-200 lg:col-span-2 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
            <BarChart3 className="h-4 w-4 text-zinc-400" /> Daily Cost & Token Consumption Trends
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-200">
                  <th className="pb-3 pr-4 font-bold uppercase">Date</th>
                  <th className="pb-3 pr-4 font-bold uppercase">Registered Model</th>
                  <th className="pb-3 pr-4 font-bold uppercase text-center">Total Runs</th>
                  <th className="pb-3 pr-4 font-bold uppercase text-right">Tokens Count</th>
                  <th className="pb-3 font-bold uppercase text-right">Pricing Cost</th>
                </tr>
              </thead>
              <tbody>
                {usage.map((u, idx) => (
                  <tr key={idx} className="border-b border-zinc-100 hover:bg-zinc-50">
                    <td className="py-3 pr-4 font-mono font-bold text-zinc-700">{u.date}</td>
                    <td className="py-3 pr-4 text-zinc-800 font-semibold">{u.model_name}</td>
                    <td className="py-3 pr-4 text-center text-zinc-600 font-bold">{u.total_calls}</td>
                    <td className="py-3 pr-4 text-right text-zinc-600 font-mono">{u.total_tokens.toLocaleString()}</td>
                    <td className="py-3 text-right font-bold text-teal-600 font-mono">${u.total_cost.toFixed(4)}</td>
                  </tr>
                ))}
                {usage.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-zinc-400 font-medium">No usage history compiled. Daily statistics aggregate overnight.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Providers Status Side Card */}
        <div className="bg-white p-6 rounded-xl border border-zinc-200 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
            <Activity className="h-4 w-4 text-zinc-400" /> Provider Integrations Status
          </h3>
          <div className="space-y-3">
            {providers.map((p, idx) => (
              <div key={idx} className="flex items-center justify-between p-3.5 bg-zinc-50 border rounded-lg hover:bg-zinc-100 transition-colors">
                <div>
                  <p className="text-xs font-bold text-zinc-800">{p.name}</p>
                  <p className="text-[10px] text-zinc-400 mt-0.5">Latency: {p.latency_ms} ms</p>
                </div>
                <span className={`px-2 py-0.5 text-[9px] font-bold border rounded-full ${
                  p.status === "online" ? "bg-emerald-100 text-emerald-800 border-emerald-200" : "bg-rose-100 text-rose-800 border-rose-200"
                }`}>
                  {p.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
