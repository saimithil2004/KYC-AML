"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { getAIPolicies, createAIPolicy } from "@/lib/api";
import type { AIPolicy } from "@/lib/types";
import {
  Brain, Plus, CheckCircle2, AlertTriangle, ShieldCheck, Sliders,
  RefreshCw, X, Save
} from "lucide-react";

export default function AIGovernancePoliciesPage() {
  const { token } = useAuth();
  const [policies, setPolicies] = useState<AIPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Modal
  const [showPolicyModal, setShowPolicyModal] = useState(false);

  // Form
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [rulesStr, setRulesStr] = useState(
    '{\n  "min_confidence_threshold": 70.0,\n  "max_latency_ms": 5000,\n  "max_cost": 0.05,\n  "manual_review_threshold": 80.0\n}'
  );

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setErrorMsg("");
      const res = await getAIPolicies(token);
      setPolicies(res);
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to load governance policies.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !name) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      let rules = {};
      try {
        rules = JSON.parse(rulesStr);
      } catch {
        throw new Error("Invalid JSON configuration format.");
      }
      await createAIPolicy(token, { name, description: desc, rules_json: rules, is_active: true });
      setSuccessMsg(`Compliance Policy '${name}' registered successfully.`);
      setName("");
      setDesc("");
      setShowPolicyModal(false);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to register policy.");
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-teal-600" />
        <span className="ml-3 text-sm text-zinc-600 font-semibold">Loading governance policies...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn text-xs">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white p-6 rounded-2xl shadow-sm border border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
            <Brain className="h-6 w-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">AI Compliance & Governance Policies</h1>
            <p className="text-xs text-zinc-400">Configure guardrails thresholds checks, model safety guidelines, and hallucination bounds</p>
          </div>
        </div>
        <button
          onClick={() => setShowPolicyModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 hover:bg-teal-500 text-xs font-semibold rounded-lg text-white transition-colors self-start md:self-auto"
        >
          <Plus className="h-4 w-4" /> Create Policy Guide
        </button>
      </div>

      {successMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm">
          <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
          <p className="font-semibold">{successMsg}</p>
        </div>
      )}

      {errorMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
          <AlertTriangle className="h-4.5 w-4.5 text-rose-500 shrink-0" />
          <p className="font-semibold">{errorMsg}</p>
        </div>
      )}

      {/* Policies Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {policies.map((p) => (
          <div key={p.id} className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4 shadow-xs relative">
            <div className="flex justify-between items-start">
              <div>
                <span className={`px-2 py-0.5 text-[9px] font-bold border rounded-full ${
                  p.is_active ? "bg-emerald-100 text-emerald-800 border-emerald-200" : "bg-zinc-100 text-zinc-800 border-zinc-200"
                }`}>
                  {p.is_active ? "ACTIVE GUARDRAIL" : "DRAFT"}
                </span>
                <h3 className="text-base font-bold text-zinc-800 mt-2 font-mono">{p.name}</h3>
                <p className="text-zinc-500 font-medium mt-1">{p.description || "No description provided."}</p>
              </div>
            </div>

            {/* Threshold Rules list */}
            <div className="space-y-2 border-t pt-3">
              <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1">
                <Sliders className="h-3.5 w-3.5 text-zinc-400" /> Active Threshold Guidelines
              </p>
              <div className="grid grid-cols-2 gap-3 text-xs">
                {Object.entries(p.rules).map(([key, val]) => (
                  <div key={key} className="p-3 bg-zinc-50 border rounded-lg">
                    <p className="text-[10px] text-zinc-400 font-bold uppercase truncate">{key.replace(/_/g, " ")}</p>
                    <p className="text-zinc-800 font-mono font-bold mt-1">{val.toString()}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
        {policies.length === 0 && (
          <div className="col-span-2 bg-white rounded-xl border border-zinc-200 p-8 text-center text-zinc-400 font-medium">
            No compliance guidelines active. Register a policy guide to enable runtime safety gates.
          </div>
        )}
      </div>

      {/* Create Policy Modal */}
      {showPolicyModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-zinc-200 max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                <ShieldCheck className="h-4.5 w-4.5 text-teal-600" /> Define AI Compliance Policy Guidelines
              </h3>
              <button onClick={() => setShowPolicyModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            <form onSubmit={handleCreatePolicy} className="space-y-4 font-semibold text-zinc-700">
              <div className="space-y-1.5">
                <label>Policy Code Identifier</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. standard_compliance_policy"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <div className="space-y-1.5">
                <label>Description Scope</label>
                <input
                  type="text"
                  placeholder="General screening guardrails policy"
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 focus:outline-teal-600"
                />
              </div>
              <div className="space-y-1.5">
                <label>Guardrail Parameters (JSON configuration)</label>
                <textarea
                  rows={6}
                  required
                  value={rulesStr}
                  onChange={(e) => setRulesStr(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-850 font-mono focus:outline-teal-600"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-zinc-950 text-white font-bold rounded-lg hover:bg-zinc-850 transition-colors flex items-center justify-center gap-1.5"
              >
                <Save className="h-4 w-4" /> Save Compliance Policy
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
