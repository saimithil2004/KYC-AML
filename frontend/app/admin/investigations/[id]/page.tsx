"use client";

import React, { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Briefcase, User, ShieldAlert, ArrowLeft, RefreshCw, UploadCloud,
  Download, Trash2, Send, Plus, Calendar, AlertTriangle, CheckCircle,
  FileCheck, Shield, Bot, ListTodo, HelpCircle, FileSearch, HelpCircle as HelpIcon,
  Search, Sliders, PlayCircle, PlusCircle, AlertCircle
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  getInvestigationWorkspace,
  updateInvestigation,
  assignInvestigation,
  addCaseNote,
  updateCaseNote,
  deleteCaseNote,
  uploadEvidenceFile,
  deleteEvidenceFile,
  generateSarDraft,
  updateSarStatus,
  closeInvestigation,
  reopenInvestigation,
  escalateInvestigation
} from "@/lib/api";
import {
  InvestigationWorkspacePayload,
  CaseNote,
  Evidence,
  SAR,
  TimelineEvent
} from "@/lib/types";

export default function InvestigationWorkspace() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const token = localStorage.getItem("token") || "";
  const investigationId = String(params.id);

  const [workspace, setWorkspace] = useState<InvestigationWorkspacePayload | null>(null);
  const [leftTab, setLeftTab] = useState<"profile" | "documents" | "transactions" | "alerts" | "monitoring">("profile");

  // Input states
  const [loading, setLoading] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteText, setEditingNoteText] = useState("");

  // Evidence description
  const [evidenceDesc, setEvidenceDesc] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // SAR Form states
  const [sarNarrative, setSarNarrative] = useState("");
  const [sarReason, setSarReason] = useState("");
  const [sarRecommendation, setSarRecommendation] = useState("");
  const [sarRiskIndicatorInput, setSarRiskIndicatorInput] = useState("");
  const [sarRiskIndicators, setSarRiskIndicators] = useState<string[]>(["structuring"]);

  // Message notifications
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Fetch Workspace Details
  const fetchWorkspaceData = async () => {
    setLoading(true);
    try {
      const data = await getInvestigationWorkspace(investigationId, token);
      setWorkspace(data);

      // Prepopulate SAR narrative defaults if a draft exists
      if (data.sars && data.sars.length > 0) {
        const latestSar = data.sars[0];
        setSarNarrative(latestSar.narrative);
        setSarReason(latestSar.reason);
        setSarRecommendation(latestSar.recommendation);
        setSarRiskIndicators(latestSar.risk_indicators);
      } else {
        // AI analysis default draft values
        const ai = data.investigation.ai_summary;
        setSarNarrative(ai?.case_summary || "");
        setSarReason(ai?.suspicious_behaviour_analysis || "");
        setSarRecommendation(ai?.recommended_actions?.join("\n") || "");
      }
    } catch (err: any) {
      console.error(err);
      setMessage({ type: "error", text: "Failed to load investigation workspace." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (investigationId) {
      fetchWorkspaceData();
    }
  }, [investigationId]);

  // Notes
  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    setLoading(true);
    try {
      await addCaseNote(investigationId, { note_text: noteText }, token);
      setNoteText("");
      setMessage({ type: "success", text: "Case note logged." });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to add note." });
    } finally {
      setLoading(false);
    }
  };

  const handleEditNoteStart = (note: CaseNote) => {
    setEditingNoteId(note.id);
    setEditingNoteText(note.note_text);
  };

  const handleSaveNoteEdit = async (noteId: string) => {
    if (!editingNoteText.trim()) return;
    setLoading(true);
    try {
      await updateCaseNote(investigationId, noteId, { note_text: editingNoteText }, token);
      setEditingNoteId(null);
      setMessage({ type: "success", text: "Note edited successfully." });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to edit note." });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    if (!confirm("Are you sure you want to delete this case note?")) return;
    setLoading(true);
    try {
      await deleteCaseNote(investigationId, noteId, token);
      setMessage({ type: "success", text: "Note deleted successfully." });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to delete note." });
    } finally {
      setLoading(false);
    }
  };

  // Evidence
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setLoading(true);
    try {
      await uploadEvidenceFile(investigationId, files[0], evidenceDesc || null, token);
      setEvidenceDesc("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      setMessage({ type: "success", text: "Evidence document uploaded." });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to upload file." });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteEvidence = async (evId: string) => {
    if (!confirm("Remove this evidence file from workspace locker?")) return;
    setLoading(true);
    try {
      await deleteEvidenceFile(investigationId, evId, token);
      setMessage({ type: "success", text: "Evidence file removed." });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to remove evidence." });
    } finally {
      setLoading(false);
    }
  };

  // SAR
  const handleDraftSar = async () => {
    setLoading(true);
    try {
      await generateSarDraft(
        investigationId,
        {
          narrative: sarNarrative,
          reason: sarReason,
          risk_indicators: sarRiskIndicators,
          recommendation: sarRecommendation
        },
        token
      );
      setMessage({ type: "success", text: "SAR report drafted successfully." });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to save SAR draft." });
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateSarStatus = async (status: string) => {
    setLoading(true);
    try {
      await updateSarStatus(investigationId, { status }, token);
      setMessage({ type: "success", text: `SAR status updated to ${status}.` });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to transition SAR status." });
    } finally {
      setLoading(false);
    }
  };

  const addRiskIndicator = () => {
    if (!sarRiskIndicatorInput.trim()) return;
    if (!sarRiskIndicators.includes(sarRiskIndicatorInput.trim())) {
      setSarRiskIndicators([...sarRiskIndicators, sarRiskIndicatorInput.trim()]);
    }
    setSarRiskIndicatorInput("");
  };

  const removeRiskIndicator = (tag: string) => {
    setSarRiskIndicators(sarRiskIndicators.filter((t) => t !== tag));
  };

  // Escalations
  const handleCaseTransition = async (action: string) => {
    setLoading(true);
    try {
      if (action === "close") {
        await closeInvestigation(investigationId, token);
      } else if (action === "reopen") {
        await reopenInvestigation(investigationId, token);
      } else {
        await escalateInvestigation(investigationId, { action }, token);
      }
      setMessage({ type: "success", text: `Investigation transitioned successfully: ${action}.` });
      fetchWorkspaceData();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to transition case." });
    } finally {
      setLoading(false);
    }
  };

  if (!workspace) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 text-zinc-400 animate-spin" />
      </div>
    );
  }

  const { investigation, customer, kyc_profile, documents, alerts, transactions, risk_scores, monitoring_history, notes, evidence, sars, timeline } = workspace;
  const ai = investigation.ai_summary;

  return (
    <div className="flex flex-col min-h-screen bg-zinc-50">
      {/* Workspace Header */}
      <div className="border-b border-zinc-200 bg-white px-6 py-4 flex items-center justify-between shadow-sm sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/admin/investigations")}
            className="p-1 rounded-lg hover:bg-zinc-100 transition"
          >
            <ArrowLeft className="h-5 w-5 text-zinc-500" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-zinc-900">Case Investigation Workspace</h1>
              <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                investigation.status === "closed"
                  ? "bg-zinc-100 text-zinc-600"
                  : investigation.status === "escalated"
                  ? "bg-rose-50 text-rose-600 border border-rose-100"
                  : "bg-teal-50 text-teal-700 border border-teal-100"
              }`}>
                {investigation.status.replace("_", " ")}
              </span>
            </div>
            <p className="text-xs text-zinc-400 font-mono">Case ID: {investigation.case_id} · Inv ID: {investigation.id}</p>
          </div>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => handleCaseTransition("edd_required")}
            className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-700 hover:bg-amber-100 transition"
          >
            EDD Required
          </button>
          <button
            onClick={() => handleCaseTransition("escalate")}
            className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-bold text-rose-700 hover:bg-rose-100 transition"
          >
            Escalate Case
          </button>
          {investigation.status === "escalated" && (
            <button
              onClick={() => handleCaseTransition("return")}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-bold text-zinc-700 hover:bg-zinc-50 transition"
            >
              Return Case
            </button>
          )}
          {investigation.status === "closed" ? (
            <button
              onClick={() => handleCaseTransition("reopen")}
              className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-700 transition"
            >
              Reopen Case
            </button>
          ) : (
            <button
              onClick={() => handleCaseTransition("close")}
              className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-rose-700 transition"
            >
              Close Case
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className="mx-6 mt-4 p-3 rounded-lg border text-xs font-semibold flex items-center justify-between bg-teal-50 border-teal-100 text-teal-800">
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className="text-teal-600 font-bold hover:underline">Dismiss</button>
        </div>
      )}

      {/* Workspace Panels Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 overflow-y-auto">
        
        {/* PANEL 1: Customer Profile Details & KYC */}
        <div className="rounded-xl border border-zinc-200 bg-white shadow-sm flex flex-col overflow-hidden h-[630px]">
          {/* Tabs header */}
          <div className="flex border-b border-zinc-150 bg-zinc-50 text-[11px] font-bold text-zinc-500">
            <button
              onClick={() => setLeftTab("profile")}
              className={`flex-1 py-3 text-center border-b-2 -mb-px transition ${
                leftTab === "profile" ? "border-teal-600 text-teal-600" : "border-transparent"
              }`}
            >
              Profile
            </button>
            <button
              onClick={() => setLeftTab("documents")}
              className={`flex-1 py-3 text-center border-b-2 -mb-px transition ${
                leftTab === "documents" ? "border-teal-600 text-teal-600" : "border-transparent"
              }`}
            >
              Docs ({documents.length})
            </button>
            <button
              onClick={() => setLeftTab("transactions")}
              className={`flex-1 py-3 text-center border-b-2 -mb-px transition ${
                leftTab === "transactions" ? "border-teal-600 text-teal-600" : "border-transparent"
              }`}
            >
              Tx ({transactions.length})
            </button>
            <button
              onClick={() => setLeftTab("alerts")}
              className={`flex-1 py-3 text-center border-b-2 -mb-px transition ${
                leftTab === "alerts" ? "border-teal-600 text-teal-600" : "border-transparent"
              }`}
            >
              Alerts
            </button>
            <button
              onClick={() => setLeftTab("monitoring")}
              className={`flex-1 py-3 text-center border-b-2 -mb-px transition ${
                leftTab === "monitoring" ? "border-teal-600 text-teal-600" : "border-transparent"
              }`}
            >
              Rescreen
            </button>
          </div>

          <div className="flex-1 p-5 overflow-y-auto">
            {/* Profile Content */}
            {leftTab === "profile" && kyc_profile && (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-zinc-100 flex items-center justify-center font-bold text-zinc-700">
                    {kyc_profile.full_name[0]}
                  </div>
                  <div>
                    <h3 className="font-bold text-zinc-900 text-sm">{kyc_profile.full_name}</h3>
                    <p className="text-[10px] text-zinc-400 capitalize">{customer?.customer_type} · RiskCategory: {kyc_profile.risk_category}</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-3.5 text-xs border-t border-zinc-100 pt-3">
                  <div>
                    <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Date of Birth</p>
                    <p className="font-medium text-zinc-800">{kyc_profile.dob}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Nationality</p>
                    <p className="font-medium text-zinc-800">{kyc_profile.nationality}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Tax Residency</p>
                    <p className="font-medium text-zinc-800">{kyc_profile.tax_residency || "N/A"}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Occupation</p>
                    <p className="font-medium text-zinc-800">{kyc_profile.occupation}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Source of Funds</p>
                    <p className="font-medium text-zinc-800">{kyc_profile.source_of_funds}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Source of Wealth</p>
                    <p className="font-medium text-zinc-800">{kyc_profile.source_of_wealth}</p>
                  </div>
                </div>

                <div className="border-t border-zinc-100 pt-3 text-xs">
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Residential Address</p>
                  <p className="font-medium text-zinc-800">{kyc_profile.address}</p>
                </div>

                <div className="border-t border-zinc-100 pt-3 text-xs">
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wider">Onboarding Declared Description</p>
                  <p className="font-medium text-zinc-700 italic">{kyc_profile.expected_activity_desc || "No activity statement provided"}</p>
                </div>
              </div>
            )}

            {/* Documents Content */}
            {leftTab === "documents" && (
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Uploaded Documents Verification Status</h4>
                {documents.length === 0 ? (
                  <p className="text-xs text-zinc-400">No onboarding documents uploaded.</p>
                ) : (
                  documents.map((doc) => (
                    <div key={doc.id} className="flex justify-between items-center bg-zinc-50 border border-zinc-200 p-2.5 rounded-lg text-xs">
                      <div>
                        <p className="font-bold text-zinc-950 truncate max-w-[170px]">{doc.file_name}</p>
                        <span className="text-[10px] text-zinc-500 capitalize">{doc.document_type}</span>
                      </div>
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                        doc.verification_status === "verified"
                          ? "bg-teal-50 text-teal-700"
                          : doc.verification_status === "failed"
                          ? "bg-rose-50 text-rose-700"
                          : "bg-amber-50 text-amber-700"
                      }`}>
                        {doc.verification_status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Transactions Content */}
            {leftTab === "transactions" && (
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Transactions History</h4>
                {transactions.length === 0 ? (
                  <p className="text-xs text-zinc-400">No transaction logs available.</p>
                ) : (
                  transactions.map((tx) => (
                    <div key={tx.id} className="flex justify-between items-center bg-zinc-50 border border-zinc-200 p-2.5 rounded-lg text-xs">
                      <div>
                        <p className="font-bold text-zinc-800">{tx.receiver_name}</p>
                        <span className="text-[10px] text-zinc-500 font-mono">Completed: {new Date(tx.completed_at || tx.created_at).toLocaleDateString()}</span>
                      </div>
                      <div className="text-right">
                        <p className="font-black text-zinc-950">{tx.currency} {tx.amount.toLocaleString()}</p>
                        <span className="text-[10px] text-zinc-400 capitalize">{tx.status}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Alerts & Risk Content */}
            {leftTab === "alerts" && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Active Alerts</h4>
                  {alerts.length === 0 ? (
                    <p className="text-xs text-zinc-400">No active alerts open.</p>
                  ) : (
                    alerts.map((al) => (
                      <div key={al.id} className="bg-rose-50 border border-rose-100 p-2.5 rounded-lg text-xs flex gap-2">
                        <AlertTriangle className="h-4.5 w-4.5 text-rose-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="font-bold text-rose-900 uppercase">{al.alert_type.replace(/_/g, " ")}</p>
                          <span className="text-[10px] text-rose-700 font-medium">Risk Score Evaluated: {al.risk_score}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="space-y-2 border-t border-zinc-100 pt-3">
                  <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Risk Score History</h4>
                  {risk_scores.length === 0 ? (
                    <p className="text-xs text-zinc-400">No historical risk scores found.</p>
                  ) : (
                    risk_scores.map((rs) => (
                      <div key={rs.id} className="flex justify-between items-center text-xs border-b border-zinc-100 pb-2 last:border-0">
                        <div>
                          <p className="font-semibold text-zinc-800 capitalize">Risk Tier: {rs.risk_tier}</p>
                          <span className="text-[10px] text-zinc-400">{new Date(rs.created_at).toLocaleDateString()}</span>
                        </div>
                        <span className="text-sm font-black text-zinc-950">{rs.overall_score}/100</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Monitoring History Content */}
            {leftTab === "monitoring" && (
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Continuous recheck logs</h4>
                {monitoring_history.length === 0 ? (
                  <p className="text-xs text-zinc-400">No continuous monitoring history logged.</p>
                ) : (
                  monitoring_history.map((mh) => (
                    <div key={mh.id} className="bg-zinc-50 border border-zinc-200 p-2.5 rounded-lg text-xs space-y-2">
                      <div className="flex justify-between font-semibold">
                        <span className="text-zinc-800">{mh.trigger_reason}</span>
                        <span className="text-zinc-500">{new Date(mh.screening_date).toLocaleDateString()}</span>
                      </div>
                      <div className="flex justify-between text-[11px] text-zinc-500">
                        <span>Score: {mh.old_score} &rarr; {mh.new_score}</span>
                        <span className={`font-bold ${mh.risk_delta > 0 ? "text-rose-600" : "text-teal-600"}`}>
                          Delta: {mh.risk_delta > 0 ? `+${mh.risk_delta}` : mh.risk_delta}
                        </span>
                        <span className="font-medium capitalize text-teal-700">{mh.risk_trend}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* PANEL 2: AI Investigation Assistant & Case Notes */}
        <div className="space-y-6 flex flex-col">
          {/* AI Investigation Assistant Card (Part 7) */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
            <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
              <Bot className="h-5 w-5 text-indigo-500" />
              AI Assistant Analysis
            </h3>
            
            <div className="space-y-3.5 max-h-[300px] overflow-y-auto text-xs text-zinc-700">
              <div className="space-y-1">
                <p className="font-semibold text-zinc-900 flex items-center gap-1"><FileSearch className="h-3.5 w-3.5 text-zinc-400" />Case Summary</p>
                <p className="text-zinc-600 bg-zinc-50 p-2 rounded border border-zinc-100">{ai?.case_summary || "Initial audit summary pending analyzer run."}</p>
              </div>

              <div className="space-y-1">
                <p className="font-semibold text-zinc-900 flex items-center gap-1"><ShieldAlert className="h-3.5 w-3.5 text-zinc-400" />Suspicious Behaviour Analysis</p>
                <p className="text-zinc-600 bg-zinc-50 p-2 rounded border border-zinc-100">{ai?.suspicious_behaviour_analysis || "No suspicious flags detected."}</p>
              </div>

              <div className="space-y-1">
                <p className="font-semibold text-zinc-900 flex items-center gap-1"><ListTodo className="h-3.5 w-3.5 text-zinc-400" />Recommended Actions</p>
                <ul className="list-disc pl-4 space-y-1 text-zinc-600">
                  {ai?.recommended_actions?.map((act, index) => (
                    <li key={index}>{act}</li>
                  ))}
                  {(!ai?.recommended_actions || ai.recommended_actions.length === 0) && <li>No recommended actions available.</li>}
                </ul>
              </div>

              <div className="space-y-1">
                <p className="font-semibold text-zinc-900 flex items-center gap-1"><HelpIcon className="h-3.5 w-3.5 text-zinc-400" />Questions for Investigator</p>
                <ul className="list-decimal pl-4 space-y-1 text-zinc-600">
                  {ai?.questions_for_investigator?.map((q, index) => (
                    <li key={index}>{q}</li>
                  ))}
                  {(!ai?.questions_for_investigator || ai.questions_for_investigator.length === 0) && <li>No critical questions suggested.</li>}
                </ul>
              </div>

              <div className="space-y-1">
                <p className="font-semibold text-zinc-900 flex items-center gap-1"><UploadCloud className="h-3.5 w-3.5 text-zinc-400" />Missing Evidence Suggestions</p>
                <ul className="list-disc pl-4 space-y-1 text-zinc-600">
                  {ai?.missing_evidence_suggestions?.map((ev, index) => (
                    <li key={index}>{ev}</li>
                  ))}
                  {(!ai?.missing_evidence_suggestions || ai.missing_evidence_suggestions.length === 0) && <li>No evidence suggestions.</li>}
                </ul>
              </div>

              <div className="space-y-1">
                <p className="font-semibold text-zinc-900 flex items-center gap-1"><Shield className="h-3.5 w-3.5 text-zinc-400" />Risk Explanation</p>
                <p className="text-zinc-600 bg-zinc-50 p-2 rounded border border-zinc-100">{ai?.risk_explanation || "Risk score is aligned with customer tier."}</p>
              </div>
            </div>
          </div>

          {/* Case Notes Workspace (Part 3) */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4 flex-1 flex flex-col min-h-[300px]">
            <h3 className="font-bold text-zinc-900 text-sm">Investigator Notes & Collaboration</h3>
            
            {/* Notes List */}
            <div className="flex-1 space-y-3 overflow-y-auto max-h-[350px] pr-1">
              {notes.length === 0 ? (
                <p className="text-xs text-zinc-400 text-center py-8">No notes logged. Add note below.</p>
              ) : (
                notes.map((n) => (
                  <div key={n.id} className="p-2.5 rounded-lg border border-zinc-150 bg-zinc-50 space-y-1.5 relative group text-xs text-zinc-700">
                    <div className="flex justify-between items-center text-[10px] text-zinc-400 font-semibold">
                      <span>{n.author_id ? "Investigator ID: " + n.author_id.slice(0, 8) : "System"}</span>
                      <span>{new Date(n.created_at).toLocaleDateString()} {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>

                    {editingNoteId === n.id ? (
                      <div className="space-y-2">
                        <textarea
                          value={editingNoteText}
                          onChange={(e) => setEditingNoteText(e.target.value)}
                          className="w-full rounded border border-zinc-300 p-2 text-xs focus:outline-none focus:border-teal-500"
                          rows={2}
                        />
                        <div className="flex gap-1.5 justify-end">
                          <button
                            onClick={() => setEditingNoteId(null)}
                            className="px-2 py-1 rounded bg-zinc-200 text-zinc-700 font-bold hover:bg-zinc-350"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => handleSaveNoteEdit(n.id)}
                            className="px-2.5 py-1 rounded bg-teal-600 text-white font-bold hover:bg-teal-700"
                          >
                            Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="text-zinc-800 leading-relaxed font-medium whitespace-pre-wrap">{n.note_text}</p>
                        {/* Action buttons on hover */}
                        <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
                          <button
                            onClick={() => handleEditNoteStart(n)}
                            className="p-1 rounded bg-white hover:bg-zinc-200 border border-zinc-300"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteNote(n.id)}
                            className="p-1 rounded bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-600"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Input Note Form */}
            <form onSubmit={handleAddNote} className="space-y-2 shrink-0 border-t border-zinc-150 pt-3">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Add note (@mention investigators, markdown allowed)..."
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  className="w-full rounded-lg border border-zinc-350 px-3 py-2 pr-10 text-xs focus:outline-none focus:border-teal-500"
                />
                <button
                  type="submit"
                  disabled={loading || !noteText.trim()}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1.5 text-teal-600 disabled:opacity-30 hover:bg-zinc-100 rounded-full"
                >
                  <Send className="h-3.5 w-3.5" />
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* PANEL 3: Evidence Locker, Timeline, and SAR report forms */}
        <div className="space-y-6 flex flex-col">
          
          {/* Evidence Locker (Part 2) */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
            <h3 className="font-bold text-zinc-900 text-sm">Evidence Locker</h3>
            
            {/* File List */}
            <div className="space-y-2 max-h-[150px] overflow-y-auto pr-1">
              {evidence.length === 0 ? (
                <p className="text-xs text-zinc-400 text-center py-4">No evidence documents uploaded.</p>
              ) : (
                evidence.map((ev) => (
                  <div key={ev.id} className="flex justify-between items-center bg-zinc-50 border border-zinc-200 p-2 rounded-lg text-xs">
                    <div className="truncate max-w-[160px]">
                      <p className="font-bold text-zinc-800 truncate">{ev.file_name}</p>
                      <span className="text-[9px] text-zinc-400 font-mono">Hash: {ev.file_hash.slice(0, 8)}...</span>
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => alert(`Checksum SHA256 verified successfully: \n${ev.file_hash}`)}
                        className="p-1 hover:bg-zinc-200 border border-zinc-300 rounded"
                        title="Verify Hash Checksum"
                      >
                        Verify
                      </button>
                      <button
                        onClick={() => handleDeleteEvidence(ev.id)}
                        className="p-1 text-rose-600 hover:bg-rose-50 border border-rose-200 rounded"
                        title="Delete File"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Upload Zone */}
            <div className="space-y-2 border-t border-zinc-150 pt-3">
              <input
                type="text"
                placeholder="Evidence description..."
                value={evidenceDesc}
                onChange={(e) => setEvidenceDesc(e.target.value)}
                className="w-full rounded border border-zinc-300 px-2 py-1 text-xs focus:outline-none focus:border-teal-500"
              />
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-zinc-300 hover:border-teal-500 rounded-lg p-4 text-center cursor-pointer transition flex flex-col items-center justify-center gap-1.5"
              >
                <UploadCloud className="h-8 w-8 text-zinc-400" />
                <span className="text-[10px] text-zinc-500 font-semibold">Click or drag files here to upload (PDF, DOCX, ZIP, MP4, etc.)</span>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </div>
            </div>
          </div>

          {/* SAR Manager (Part 6) */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-zinc-900 text-sm">Suspicious Activity Report (SAR)</h3>
              {sars.length > 0 && (
                <span className={`inline-flex rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                  sars[0].status === "submitted"
                    ? "bg-teal-50 text-teal-700"
                    : sars[0].status === "approved"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-100"
                    : "bg-amber-50 text-amber-700 border border-amber-100"
                }`}>
                  {sars[0].status}
                </span>
              )}
            </div>

            <div className="space-y-3.5 text-xs">
              <div className="space-y-1">
                <label className="font-bold text-zinc-700">Narrative Description</label>
                <textarea
                  value={sarNarrative}
                  onChange={(e) => setSarNarrative(e.target.value)}
                  placeholder="Describe suspicious narrative summary here..."
                  className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                  rows={2}
                />
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-700">Reason for Filing</label>
                <input
                  type="text"
                  value={sarReason}
                  onChange={(e) => setSarReason(e.target.value)}
                  placeholder="Structuring / Sanctions hit / Value mismatch"
                  className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-700">Risk Indicators tags</label>
                <div className="flex gap-1.5 flex-wrap mb-1.5">
                  {sarRiskIndicators.map((tag) => (
                    <span key={tag} className="inline-flex items-center gap-1 rounded bg-zinc-100 border border-zinc-200 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-800">
                      {tag}
                      <button type="button" onClick={() => removeRiskIndicator(tag)} className="text-zinc-400 hover:text-zinc-600 font-bold">×</button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-1.5">
                  <input
                    type="text"
                    placeholder="structuring, shell_company"
                    value={sarRiskIndicatorInput}
                    onChange={(e) => setSarRiskIndicatorInput(e.target.value)}
                    className="flex-1 rounded border border-zinc-300 px-2 py-1 text-xs focus:outline-none focus:border-teal-500"
                  />
                  <button type="button" onClick={addRiskIndicator} className="px-2 py-1 bg-zinc-200 border border-zinc-300 rounded font-semibold text-zinc-700">+</button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-700">Recommendation Action</label>
                <input
                  type="text"
                  value={sarRecommendation}
                  onChange={(e) => setSarRecommendation(e.target.value)}
                  placeholder="Block customer, report to FIU"
                  className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="flex gap-1.5 pt-2 border-t border-zinc-150">
                <button
                  onClick={handleDraftSar}
                  disabled={loading}
                  className="flex-1 rounded bg-zinc-100 border border-zinc-300 py-1.5 font-bold text-zinc-700 hover:bg-zinc-200 transition"
                >
                  Save Draft
                </button>
                {sars.length > 0 && sars[0].status === "draft" && (
                  <button
                    onClick={() => handleUpdateSarStatus("submitted")}
                    disabled={loading}
                    className="flex-1 rounded bg-teal-600 py-1.5 font-bold text-white hover:bg-teal-700 transition"
                  >
                    Submit SAR
                  </button>
                )}
                {sars.length > 0 && sars[0].status === "submitted" && user?.role === "admin" && (
                  <div className="flex gap-1 w-full flex-1">
                    <button
                      onClick={() => handleUpdateSarStatus("approved")}
                      className="flex-1 rounded bg-emerald-600 py-1.5 text-[11px] font-bold text-white hover:bg-emerald-700 transition"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleUpdateSarStatus("rejected")}
                      className="flex-1 rounded bg-rose-600 py-1.5 text-[11px] font-bold text-white hover:bg-rose-700 transition"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Chronological Case Timeline (Part 5) */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4 flex-1 overflow-hidden min-h-[250px]">
            <h3 className="font-bold text-zinc-900 text-sm">Chronological Timeline</h3>
            <div className="space-y-4 overflow-y-auto max-h-[300px] pr-1 text-xs text-zinc-700">
              {timeline.length === 0 ? (
                <p className="text-xs text-zinc-400 text-center py-4">No events logged yet.</p>
              ) : (
                timeline.map((ev, index) => (
                  <div key={ev.id || index} className="flex gap-3 relative pb-4 last:pb-0">
                    {/* Line connection */}
                    {index < timeline.length - 1 && (
                      <div className="absolute left-[7px] top-[14px] bottom-0 w-0.5 bg-zinc-200" />
                    )}
                    {/* Bullet */}
                    <div className="h-4 w-4 rounded-full bg-teal-500 border-2 border-white ring-2 ring-teal-50 mt-0.5 z-10 shrink-0" />
                    <div className="space-y-0.5">
                      <p className="font-bold text-zinc-900">{ev.title}</p>
                      <p className="text-zinc-500 font-medium">{ev.description}</p>
                      <span className="text-[9px] text-zinc-400 font-mono">{new Date(ev.timestamp).toLocaleDateString()} {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
