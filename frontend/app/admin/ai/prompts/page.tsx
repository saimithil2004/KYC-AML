"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  getAIPrompts, createPromptTemplate, createPromptVersion, deletePromptTemplate,
  approvePromptVersion, rejectPromptVersion, rollbackPromptVersion
} from "@/lib/api";
import type { PromptTemplate, PromptVersion } from "@/lib/types";
import {
  FileCode, Plus, CheckCircle2, AlertTriangle, ArrowLeftRight, RotateCcw,
  Check, X, RefreshCw, Terminal, Play, Eye
} from "lucide-react";

export default function PromptManagementPage() {
  const { token } = useAuth();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Modals
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");

  // Form states
  const [templateName, setTemplateName] = useState("");
  const [templateDesc, setTemplateDesc] = useState("");
  const [versionContent, setVersionContent] = useState("");
  const [versionName, setVersionName] = useState("");

  // Diffs & Compares
  const [compareTemplate, setCompareTemplate] = useState<PromptTemplate | null>(null);
  const [v1, setV1] = useState<PromptVersion | null>(null);
  const [v2, setV2] = useState<PromptVersion | null>(null);
  const [diffResult, setDiffResult] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setErrorMsg("");
      const res = await getAIPrompts(token);
      setTemplates(res);
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to load prompts template settings.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !templateName) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await createPromptTemplate(token, { name: templateName, description: templateDesc });
      setSuccessMsg(`Prompt template '${templateName}' registered.`);
      setTemplateName("");
      setTemplateDesc("");
      setShowTemplateModal(false);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create prompt template.");
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedTemplateId || !versionContent || !versionName) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await createPromptVersion(token, selectedTemplateId, {
        content: versionContent,
        version: versionName,
        status: "draft"
      });
      setSuccessMsg(`Prompt version '${versionName}' added as draft.`);
      setVersionContent("");
      setVersionName("");
      setShowVersionModal(false);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to add version.");
    }
  };

  const handleApprove = async (id: string) => {
    if (!token || !confirm("Approve this prompt version?")) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await approvePromptVersion(token, { version_id: id });
      setSuccessMsg("Prompt version approved successfully.");
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to approve prompt.");
    }
  };

  const handleReject = async (id: string) => {
    if (!token || !confirm("Reject this prompt version?")) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await rejectPromptVersion(token, { version_id: id });
      setSuccessMsg("Prompt version rejected.");
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to reject prompt.");
    }
  };

  const handleRollback = async (templateId: string, versionId: string) => {
    if (!token || !confirm("Activate this prompt version? (Will rollback other active versions)")) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await rollbackPromptVersion(token, { template_id: templateId, target_version_id: versionId });
      setSuccessMsg("Configuration rolled back successfully.");
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to switch active version.");
    }
  };

  const runDiff = () => {
    if (!v1 || !v2) return;
    // Simple line diff visualization
    const diffLines: string[] = [];
    const lines1 = v1.content.split("\n");
    const lines2 = v2.content.split("\n");
    const maxLines = Math.max(lines1.length, lines2.length);
    for (let i = 0; i < maxLines; i++) {
      const l1 = lines1[i] || "";
      const l2 = lines2[i] || "";
      if (l1 !== l2) {
        if (l1) diffLines.push(`- L${i + 1}: ${l1}`);
        if (l2) diffLines.push(`+ L${i + 1}: ${l2}`);
      } else {
        diffLines.push(`  L${i + 1}: ${l1}`);
      }
    }
    setDiffResult(diffLines.join("\n"));
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-teal-600" />
        <span className="ml-3 text-sm text-zinc-600 font-semibold">Loading prompts manager...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn text-xs">
      {/* Header */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white p-6 rounded-2xl shadow-sm border border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
            <FileCode className="h-6 w-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Prompt Version Management</h1>
            <p className="text-xs text-zinc-400">Control system prompts version histories, run pre-approval tests and deploy updates safely</p>
          </div>
        </div>
        <button
          onClick={() => setShowTemplateModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 hover:bg-teal-500 text-xs font-semibold rounded-lg text-white transition-colors self-start md:self-auto"
        >
          <Plus className="h-4 w-4" /> Create Prompt Group
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

      {/* Templates List */}
      <div className="space-y-6">
        {templates.map((temp) => (
          <div key={temp.id} className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4 shadow-xs">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <h3 className="text-sm font-bold text-zinc-800 font-mono">{temp.name}</h3>
                <p className="text-zinc-500 font-medium mt-1">{temp.description || "No description provided."}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setCompareTemplate(temp);
                    setV1(null);
                    setV2(null);
                    setDiffResult(null);
                  }}
                  className="px-2.5 py-1.5 border hover:bg-zinc-50 font-bold text-zinc-600 rounded-md transition-colors flex items-center gap-1"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5" /> Compare Revisions
                </button>
                <button
                  onClick={() => {
                    setSelectedTemplateId(temp.id);
                    setShowVersionModal(true);
                  }}
                  className="px-2.5 py-1.5 bg-zinc-900 text-white hover:bg-zinc-850 font-bold rounded-md transition-colors flex items-center gap-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Draft version
                </button>
              </div>
            </div>

            {/* Version List under Template */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-zinc-700">
                <thead>
                  <tr className="text-zinc-400 font-bold border-b border-zinc-100 uppercase text-[10px]">
                    <th className="pb-2">Version</th>
                    <th className="pb-2">Prompt Draft Content snippet</th>
                    <th className="pb-2">Approval Status</th>
                    <th className="pb-2">Deploy Status</th>
                    <th className="pb-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {temp.versions.map((ver) => (
                    <tr key={ver.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="py-3 font-mono font-bold">{ver.version}</td>
                      <td className="py-3 font-mono text-zinc-500 truncate max-w-md">{ver.content}</td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${
                          ver.approved_status === "approved" || ver.approved_status === "published"
                            ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                            : ver.approved_status === "rejected"
                            ? "bg-rose-100 text-rose-800 border-rose-200"
                            : "bg-amber-100 text-amber-800 border-amber-200"
                        }`}>
                          {ver.approved_status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3">
                        {ver.is_active ? (
                          <span className="flex items-center gap-1 text-emerald-600 font-bold">
                            <Check className="h-3.5 w-3.5" /> Active in production
                          </span>
                        ) : (
                          <span className="text-zinc-400">Inactive</span>
                        )}
                      </td>
                      <td className="py-3 text-right space-x-2">
                        {ver.approved_status === "pending" && (
                          <>
                            <button
                              onClick={() => handleApprove(ver.id)}
                              className="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-md"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(ver.id)}
                              className="px-2 py-1 bg-rose-600 hover:bg-rose-500 text-white font-bold rounded-md"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {(ver.approved_status === "approved" || ver.approved_status === "published") && !ver.is_active && (
                          <button
                            onClick={() => handleRollback(temp.id, ver.id)}
                            className="px-2 py-1 border hover:bg-zinc-50 font-bold text-zinc-700 rounded-md flex items-center gap-1 inline-flex"
                          >
                            <RotateCcw className="h-3.5 w-3.5 text-zinc-500" /> Activate version
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {temp.versions.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-zinc-400 font-medium">No revision logs compiled. Add version draft snapshot first.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>

      {/* Compare Modal Panel */}
      {compareTemplate && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-zinc-200 max-w-2xl w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                <ArrowLeftRight className="h-4.5 w-4.5 text-teal-600" /> Compare Template Revisions: {compareTemplate.name}
              </h3>
              <button onClick={() => setCompareTemplate(null)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="font-bold text-zinc-600 mb-1.5 block">Revision Source</label>
                <select
                  onChange={(e) => setV1(compareTemplate.versions.find(v => v.id === e.target.value) || null)}
                  className="w-full border rounded-lg p-2.5 text-zinc-850"
                  defaultValue=""
                >
                  <option value="" disabled>Select Version</option>
                  {compareTemplate.versions.map(v => (
                    <option key={v.id} value={v.id}>{v.version} ({v.approved_status})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-bold text-zinc-600 mb-1.5 block">Revision Target</label>
                <select
                  onChange={(e) => setV2(compareTemplate.versions.find(v => v.id === e.target.value) || null)}
                  className="w-full border rounded-lg p-2.5 text-zinc-850"
                  defaultValue=""
                >
                  <option value="" disabled>Select Version</option>
                  {compareTemplate.versions.map(v => (
                    <option key={v.id} value={v.id}>{v.version} ({v.approved_status})</option>
                  ))}
                </select>
              </div>
            </div>
            {v1 && v2 && (
              <button
                onClick={runDiff}
                className="w-full py-2 bg-zinc-900 text-white font-bold rounded-lg hover:bg-zinc-850 transition-colors"
              >
                Compute Diff comparison
              </button>
            )}
            {diffResult && (
              <pre className="bg-zinc-50 border rounded-lg p-4 font-mono overflow-auto max-h-60 text-zinc-700 leading-relaxed">
                {diffResult}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Register Template Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-zinc-200 max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                <FileCode className="h-4.5 w-4.5 text-teal-600" /> Create Prompt Template
              </h3>
              <button onClick={() => setShowTemplateModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            <form onSubmit={handleCreateTemplate} className="space-y-4 font-semibold text-zinc-700">
              <div className="space-y-1.5">
                <label>Group Unique Name (e.g. sanctions_agent_prompt)</label>
                <input
                  type="text"
                  required
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <div className="space-y-1.5">
                <label>Description Scope</label>
                <input
                  type="text"
                  value={templateDesc}
                  onChange={(e) => setTemplateDesc(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 focus:outline-teal-600"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-zinc-900 text-white font-bold rounded-lg hover:bg-zinc-850 transition-colors"
              >
                Create Prompt Template Group
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Add Draft Modal */}
      {showVersionModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-zinc-200 max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                <Plus className="h-4.5 w-4.5 text-teal-600" /> Add Prompt Draft Revision Version
              </h3>
              <button onClick={() => setShowVersionModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            <form onSubmit={handleCreateVersion} className="space-y-4 font-semibold text-zinc-700">
              <div className="space-y-1.5">
                <label>Version Name (e.g. 1.0.0, 1.1.0-draft)</label>
                <input
                  type="text"
                  required
                  value={versionName}
                  onChange={(e) => setVersionName(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <div className="space-y-1.5">
                <label>Prompt Body / Instruction Guidelines</label>
                <textarea
                  rows={6}
                  required
                  value={versionContent}
                  onChange={(e) => setVersionContent(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-zinc-900 text-white font-bold rounded-lg hover:bg-zinc-850 transition-colors"
              >
                Submit Draft Version
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
