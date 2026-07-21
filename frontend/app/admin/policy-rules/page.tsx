"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  listPolicyRules,
  createPolicyRule,
  updatePolicyRule,
  deletePolicyRule,
  listRegulations,
} from "@/lib/api";
import type { PolicyRule, Regulation, Paginated } from "@/lib/types";
import {
  Sliders, Search, Plus, RefreshCw, AlertTriangle, ShieldCheck, HelpCircle,
  XCircle, CheckCircle, Edit, Trash2, BookOpen, AlertCircle, ToggleLeft, ToggleRight,
} from "lucide-react";

const PAGE_SIZE = 20;

export default function PolicyRulesPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [data, setData] = useState<Paginated<PolicyRule> | null>(null);
  const [regulations, setRegulations] = useState<Regulation[]>([]);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState("");
  const [filterCountry, setFilterCountry] = useState("");
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);
  const [loading, setLoading] = useState(false);

  // Editor Modal States
  const [editorOpen, setEditorOpen] = useState(false);
  const [editRule, setEditRule] = useState<PolicyRule | null>(null);
  const [editorError, setEditorError] = useState("");
  const [saving, setSaving] = useState(false);

  // Form Fields
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState("threshold");
  const [formRegulationId, setFormRegulationId] = useState("");
  const [formConditionsJson, setFormConditionsJson] = useState("{}");
  const [formSeverity, setFormSeverity] = useState("medium");
  const [formDescription, setFormDescription] = useState("");
  const [formExpression, setFormExpression] = useState("");
  const [formThreshold, setFormThreshold] = useState("");
  const [formCountry, setFormCountry] = useState("");
  const [formVersion, setFormVersion] = useState("1.0.0");

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listPolicyRules(token, {
        page,
        page_size: PAGE_SIZE,
        rule_type: filterType || undefined,
        is_active: filterActive,
        country: filterCountry || undefined,
      });
      setData(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, page, filterType, filterActive, filterCountry]);

  const fetchRegulations = useCallback(async () => {
    if (!token) return;
    try {
      const result = await listRegulations(token, { page: 1, page_size: 100 });
      setRegulations(result.items);
      if (result.items.length > 0) {
        setFormRegulationId(result.items[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  }, [token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (token) {
      fetchRegulations();
    }
  }, [token, fetchRegulations]);

  const handleOpenCreate = () => {
    setEditRule(null);
    setFormName("");
    setFormType("threshold");
    setFormConditionsJson("{}");
    setFormSeverity("medium");
    setFormDescription("");
    setFormExpression("");
    setFormThreshold("");
    setFormCountry("");
    setFormVersion("1.0.0");
    setEditorError("");
    setEditorOpen(true);
  };

  const handleOpenEdit = (rule: PolicyRule) => {
    setEditRule(rule);
    setFormName(rule.rule_name);
    setFormType(rule.rule_type);
    setFormRegulationId(rule.regulation_id);
    setFormConditionsJson(JSON.stringify(rule.conditions));
    setFormSeverity(rule.severity);
    setFormDescription(rule.description || "");
    setFormExpression(rule.expression || "");
    setFormThreshold(rule.threshold !== null && rule.threshold !== undefined ? String(rule.threshold) : "");
    setFormCountry(rule.country || "");
    setFormVersion(rule.version);
    setEditorError("");
    setEditorOpen(true);
  };

  const handleToggleActive = async (rule: PolicyRule) => {
    if (!token || !isAdmin) return;
    try {
      await updatePolicyRule(rule.id, { is_active: !rule.is_active }, token);
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteRule = async (id: string) => {
    if (!token || !isAdmin) return;
    if (!confirm("Are you sure you want to delete this policy rule?")) return;
    try {
      await deletePolicyRule(id, token);
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditorSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    let parsedConditions = {};
    try {
      parsedConditions = JSON.parse(formConditionsJson);
    } catch (err) {
      setEditorError("Conditions must be valid JSON.");
      return;
    }

    setSaving(true);
    setEditorError("");

    const payload = {
      regulation_id: formRegulationId,
      rule_name: formName,
      rule_type: formType,
      conditions: parsedConditions,
      severity: formSeverity,
      description: formDescription || null,
      expression: formExpression || null,
      threshold: formThreshold ? parseFloat(formThreshold) : null,
      country: formCountry || null,
      version: formVersion,
    };

    try {
      if (editRule) {
        await updatePolicyRule(editRule.id, payload, token);
      } else {
        await createPolicyRule(payload, token);
      }
      setEditorOpen(false);
      fetchData();
    } catch (err: any) {
      setEditorError(err.message || "Failed to save policy rule");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in text-zinc-800 dark:text-zinc-200">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white flex items-center gap-2">
            <Sliders className="text-teal-600 h-6.5 w-6.5" /> Policy & AML Compliance Rules
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Manage AML thresholds, blocks, EDD, and custom internal policy evaluations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm hover:bg-zinc-50 transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {isAdmin && (
            <button
              onClick={handleOpenCreate}
              className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-sm font-bold text-white hover:bg-teal-700 transition shadow-sm"
            >
              <Plus className="h-4 w-4" />
              Create Custom Rule
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={filterType}
          onChange={(e) => {
            setFilterType(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Rule Types</option>
          <option value="threshold">Threshold</option>
          <option value="block">Block</option>
          <option value="edd">EDD Trigger</option>
          <option value="aml">AML Checks</option>
          <option value="kyc">KYC Checks</option>
          <option value="internal">Internal Rules</option>
        </select>

        <select
          value={filterActive === undefined ? "" : String(filterActive)}
          onChange={(e) => {
            const v = e.target.value;
            setFilterActive(v === "" ? undefined : v === "true");
            setPage(1);
          }}
          className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="true">Active Only</option>
          <option value="false">Disabled Only</option>
        </select>

        <input
          type="text"
          placeholder="Filter country..."
          value={filterCountry}
          onChange={(e) => {
            setFilterCountry(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        />
      </div>

      {/* Policy Rule Grid */}
      <div className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-16">
            <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        ) : !data?.items.length ? (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-12 text-center text-zinc-400">
            <Sliders className="h-8 w-8 mx-auto mb-2 text-zinc-350" />
            <p className="text-sm">No policy rules configured</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
            <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-850 text-xs">
              <thead className="bg-zinc-50 dark:bg-zinc-900/50">
                <tr>
                  <th className="px-4 py-3 text-left font-bold text-zinc-500 uppercase tracking-wider">Rule Name</th>
                  <th className="px-4 py-3 text-left font-bold text-zinc-500 uppercase tracking-wider">Type</th>
                  <th className="px-4 py-3 text-left font-bold text-zinc-500 uppercase tracking-wider">Severity</th>
                  <th className="px-4 py-3 text-left font-bold text-zinc-500 uppercase tracking-wider">Target Country</th>
                  <th className="px-4 py-3 text-left font-bold text-zinc-500 uppercase tracking-wider">Status</th>
                  {isAdmin && (
                    <th className="px-4 py-3 text-right font-bold text-zinc-500 uppercase tracking-wider">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-850">
                {data.items.map((rule) => (
                  <tr key={rule.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-850">
                    <td className="px-4 py-3">
                      <p className="font-bold text-zinc-900 dark:text-white font-mono">{rule.rule_name}</p>
                      <p className="text-[10px] text-zinc-400 mt-0.5 line-clamp-1">{rule.description || "No description."}</p>
                    </td>
                    <td className="px-4 py-3 capitalize">{rule.rule_type}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        rule.severity === "critical"
                          ? "bg-red-50 dark:bg-red-950/20 text-red-700"
                          : rule.severity === "high"
                          ? "bg-orange-50 dark:bg-orange-950/20 text-orange-700"
                          : "bg-zinc-100 dark:bg-zinc-800 text-zinc-650"
                      }`}>
                        {rule.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">{rule.country || "All"}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleActive(rule)}
                        disabled={!isAdmin}
                        className={`flex items-center gap-1 text-xs font-semibold focus:outline-none ${
                          rule.is_active ? "text-emerald-600" : "text-zinc-400"
                        }`}
                      >
                        {rule.is_active ? (
                          <>
                            <ToggleRight className="h-5.5 w-5.5" />
                            <span>Active</span>
                          </>
                        ) : (
                          <>
                            <ToggleLeft className="h-5.5 w-5.5" />
                            <span>Disabled</span>
                          </>
                        )}
                      </button>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => handleOpenEdit(rule)}
                          className="text-zinc-450 hover:text-teal-600 inline-block p-1"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule.id)}
                          className="text-zinc-455 hover:text-rose-600 inline-block p-1"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Editor Dialog Confirmation modal */}
      {editorOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-xl bg-white dark:bg-zinc-900 rounded-xl border border-zinc-250 dark:border-zinc-850 p-6 space-y-4 shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-white uppercase tracking-wider border-b pb-2.5 dark:border-zinc-800">
              {editRule ? "Edit Policy Rule" : "Create Custom Compliance Rule"}
            </h3>

            {editorError && (
              <div className="p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 rounded-lg text-xs text-red-700">
                {editorError}
              </div>
            )}

            <form onSubmit={handleEditorSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Rule Name (Snake Case) *</label>
                  <input
                    type="text"
                    required
                    value={formName}
                    onChange={(e) => setFormName(e.target.value.toUpperCase().replace(/\s+/g, "_"))}
                    placeholder="e.g. UK_LARGE_TRANSACTION_LIMIT"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Rule Type *</label>
                  <select
                    value={formType}
                    onChange={(e) => setFormType(e.target.value)}
                    className="w-full rounded border px-3 py-2.5 dark:bg-zinc-800 dark:border-zinc-700"
                  >
                    <option value="threshold">Threshold</option>
                    <option value="block">Block</option>
                    <option value="edd">EDD Trigger</option>
                    <option value="aml">AML Checks</option>
                    <option value="kyc">KYC Checks</option>
                    <option value="internal">Internal Rules</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Severity *</label>
                  <select
                    value={formSeverity}
                    onChange={(e) => setFormSeverity(e.target.value)}
                    className="w-full rounded border px-3 py-2.5 dark:bg-zinc-800 dark:border-zinc-700"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Regulated Country</label>
                  <input
                    type="text"
                    value={formCountry}
                    onChange={(e) => setFormCountry(e.target.value)}
                    placeholder="e.g. United Kingdom"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Source Regulation *</label>
                  <select
                    value={formRegulationId}
                    onChange={(e) => setFormRegulationId(e.target.value)}
                    className="w-full rounded border px-3 py-2.5 dark:bg-zinc-800 dark:border-zinc-700 text-[11px]"
                  >
                    {regulations.map((reg) => (
                      <option key={reg.id} value={reg.id}>
                        {reg.title} (v{reg.version})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Numeric Threshold Value</label>
                  <input
                    type="number"
                    step="any"
                    value={formThreshold}
                    onChange={(e) => setFormThreshold(e.target.value)}
                    placeholder="e.g. 10000"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Rule Logic Version</label>
                  <input
                    type="text"
                    value={formVersion}
                    onChange={(e) => setFormVersion(e.target.value)}
                    placeholder="e.g. 1.0.0"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-650 dark:text-zinc-400">Mathematical Expression</label>
                <input
                  type="text"
                  value={formExpression}
                  onChange={(e) => setFormExpression(e.target.value)}
                  placeholder="e.g. transaction_amount > 10000"
                  className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                />
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-650 dark:text-zinc-400">Rule Description</label>
                <textarea
                  rows={2}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Triggers warning if customer is a PEP match..."
                  className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                />
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-650 dark:text-zinc-400">Evaluation JSON Conditions *</label>
                <textarea
                  rows={4}
                  value={formConditionsJson}
                  onChange={(e) => setFormConditionsJson(e.target.value)}
                  placeholder='e.g. { "max_transaction_amount": 10000 }'
                  className="w-full rounded border px-3 py-2 font-mono text-[10px] dark:bg-zinc-800 dark:border-zinc-700"
                />
              </div>

              <div className="flex gap-2 justify-end pt-3 border-t dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setEditorOpen(false)}
                  className="rounded border px-4 py-2 font-semibold hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded bg-teal-600 hover:bg-teal-700 text-white font-bold px-6 py-2 disabled:opacity-50"
                >
                  {saving ? "Saving Rule…" : "Save Rule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
