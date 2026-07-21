"use client";

import React, { useEffect, useState } from "react";
import {
  FileText, Plus, Calendar, Settings, Trash2, Download, RefreshCw,
  Search, Sliders, PlayCircle, PlusCircle, AlertCircle, FileSpreadsheet,
  FileJson, Clock, BookOpen, UserPlus
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  listReports,
  generateReport,
  deleteReport,
  listReportTemplates,
  createReportTemplate,
  deleteReportTemplate,
  listReportSchedules,
  createReportSchedule,
  deleteReportSchedule
} from "@/lib/api";
import { Report, ReportTemplate, ScheduledReport } from "@/lib/types";

export default function ReportsWorkspace() {
  const { user } = useAuth();
  const token = localStorage.getItem("token") || "";

  const [activeSubTab, setActiveSubTab] = useState<"library" | "templates" | "schedules">("library");
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [schedules, setSchedules] = useState<ScheduledReport[]>([]);
  const [errMessage, setErrMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Form inputs
  const [reportName, setReportName] = useState("");
  const [reportFormat, setReportFormat] = useState<"pdf" | "excel" | "csv" | "json">("pdf");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [reportType, setReportType] = useState("customer_summary");

  // Template Form
  const [tmplName, setTmplName] = useState("");
  const [tmplDesc, setTmplDesc] = useState("");
  const [tmplFormat, setTmplFormat] = useState("pdf");
  const [tmplReportType, setTmplReportType] = useState("customer_summary");

  // Schedule Form
  const [schedName, setSchedName] = useState("");
  const [schedTmplId, setSchedTmplId] = useState("");
  const [schedCron, setSchedCron] = useState("daily");

  const fetchData = async () => {
    setLoading(true);
    setErrMessage("");
    try {
      if (activeSubTab === "library") {
        const reps = await listReports(token);
        setReports(reps);
        const tmpls = await listReportTemplates(token);
        setTemplates(tmpls);
      } else if (activeSubTab === "templates") {
        const tmpls = await listReportTemplates(token);
        setTemplates(tmpls);
      } else if (activeSubTab === "schedules") {
        const schs = await listReportSchedules(token);
        setSchedules(schs);
        const tmpls = await listReportTemplates(token);
        setTemplates(tmpls);
      }
    } catch (err: any) {
      console.error(err);
      setErrMessage("Failed to retrieve reports operations feed.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeSubTab]);

  // Actions
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportName.trim()) return;
    setLoading(true);
    setErrMessage("");
    setSuccessMessage("");
    try {
      await generateReport(token, {
        name: reportName,
        format: reportFormat,
        filters: {
          report_type: reportType,
          template_id: selectedTemplateId || undefined
        }
      });
      setReportName("");
      setSuccessMessage("Report queued and compiled successfully.");
      fetchData();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to generate report.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteReport = async (id: string) => {
    if (!confirm("Are you sure you want to delete this report?")) return;
    setLoading(true);
    try {
      await deleteReport(id, token);
      setSuccessMessage("Report deleted successfully.");
      fetchData();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to delete report.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tmplName.trim()) return;
    setLoading(true);
    setErrMessage("");
    try {
      await createReportTemplate(token, {
        name: tmplName,
        description: tmplDesc || undefined,
        config: {
          format: tmplFormat,
          filters: { report_type: tmplReportType }
        }
      });
      setTmplName("");
      setTmplDesc("");
      setSuccessMessage("Custom report template saved.");
      fetchData();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to create template.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    if (!confirm("Delete this template? Schedules linked to it will fail.")) return;
    setLoading(true);
    try {
      await deleteReportTemplate(id, token);
      setSuccessMessage("Template deleted.");
      fetchData();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to delete template.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!schedName.trim() || !schedTmplId) return;
    setLoading(true);
    setErrMessage("");
    try {
      await createReportSchedule(token, {
        name: schedName,
        template_id: schedTmplId,
        cron_expression: schedCron
      });
      setSchedName("");
      setSuccessMessage("Report schedule created successfully.");
      fetchData();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to register schedule.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSchedule = async (id: string) => {
    if (!confirm("Remove this schedule?")) return;
    setLoading(true);
    try {
      await deleteReportSchedule(id, token);
      setSuccessMessage("Schedule removed.");
      fetchData();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to remove schedule.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (rep: Report) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    window.open(`${apiBase}/reports/${rep.id}?download=true`, "_blank");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-zinc-950 dark:text-white flex items-center gap-2">
            <FileText className="text-teal-600 h-6 w-6" /> Reports & Schedules
          </h1>
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-400">
            Build custom compliance audits, review generated file archives, and manage cron schedules
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 transition disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 text-zinc-500 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {errMessage && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-100 text-rose-800 text-sm font-semibold">
          {errMessage}
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-lg bg-teal-50 border border-teal-100 text-teal-800 text-sm font-semibold">
          {successMessage}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-zinc-200 gap-1 overflow-x-auto pb-px">
        <button
          onClick={() => setActiveSubTab("library")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
            activeSubTab === "library" ? "border-teal-600 text-teal-600" : "border-transparent text-zinc-500 hover:text-zinc-700"
          }`}
        >
          <BookOpen className="h-4 w-4" />
          Report Library
        </button>
        <button
          onClick={() => setActiveSubTab("templates")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
            activeSubTab === "templates" ? "border-teal-600 text-teal-600" : "border-transparent text-zinc-500 hover:text-zinc-700"
          }`}
        >
          <Sliders className="h-4 w-4" />
          Report Builder Templates
        </button>
        <button
          onClick={() => setActiveSubTab("schedules")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
            activeSubTab === "schedules" ? "border-teal-600 text-teal-600" : "border-transparent text-zinc-500 hover:text-zinc-700"
          }`}
        >
          <Clock className="h-4 w-4" />
          Scheduled Crons
        </button>
      </div>

      {/* Main panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Lists */}
        <div className="lg:col-span-2 space-y-4 bg-white border border-zinc-200 rounded-xl p-5 shadow-sm">
          
          {activeSubTab === "library" && (
            <div className="space-y-4">
              <h3 className="font-bold text-zinc-900 text-sm">Compiled Compliance Documents</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-zinc-200 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                      <th className="p-3">Report Name</th>
                      <th className="p-3">Format</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Generated Date</th>
                      <th className="p-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-150 text-xs text-zinc-700">
                    {reports.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-zinc-400">
                          No compiled reports available. Create one using the builder on the right!
                        </td>
                      </tr>
                    ) : (
                      reports.map((rep) => (
                        <tr key={rep.id} className="hover:bg-zinc-50/50">
                          <td className="p-3 font-semibold text-zinc-900">{rep.name}</td>
                          <td className="p-3 capitalize font-mono text-[10px]">{rep.format}</td>
                          <td className="p-3 text-zinc-500 capitalize">{rep.filters.report_type?.replace(/_/g, " ") || "custom"}</td>
                          <td className="p-3 text-zinc-500">{new Date(rep.created_at).toLocaleDateString()} {new Date(rep.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                          <td className="p-3 text-right space-x-1">
                            <button
                              onClick={() => handleDownload(rep)}
                              className="inline-flex items-center gap-1 rounded bg-teal-600 hover:bg-teal-700 px-2.5 py-1 text-[11px] font-bold text-white shadow-sm transition"
                            >
                              <Download className="h-3 w-3" /> Download
                            </button>
                            <button
                              onClick={() => handleDeleteReport(rep.id)}
                              className="inline-flex items-center rounded border border-rose-200 bg-rose-50 hover:bg-rose-100 p-1 text-rose-600"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeSubTab === "templates" && (
            <div className="space-y-4">
              <h3 className="font-bold text-zinc-900 text-sm">Saved Custom Report Templates</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {templates.map((tmpl) => (
                  <div key={tmpl.id} className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/50 space-y-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-bold text-zinc-900 text-xs">{tmpl.name}</h4>
                        <span className="text-[9px] text-zinc-400 capitalize">{tmpl.config.filters?.report_type?.replace(/_/g, " ")} ({tmpl.config.format})</span>
                      </div>
                      <button
                        onClick={() => handleDeleteTemplate(tmpl.id)}
                        className="text-rose-600 hover:text-rose-800 p-1 rounded hover:bg-rose-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="text-xs text-zinc-500 leading-relaxed truncate">{tmpl.description || "No description provided."}</p>
                  </div>
                ))}
                {templates.length === 0 && (
                  <p className="text-xs text-zinc-400 col-span-2 text-center py-8">No custom templates saved.</p>
                )}
              </div>
            </div>
          )}

          {activeSubTab === "schedules" && (
            <div className="space-y-4">
              <h3 className="font-bold text-zinc-900 text-sm">Active Scheduled Reports (Cron Rules)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-zinc-200 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                      <th className="p-3">Schedule Name</th>
                      <th className="p-3">Frequency</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Next Scheduled Execution</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-150 text-xs text-zinc-700">
                    {schedules.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-zinc-400">
                          No scheduled report executions found. Add scheduler rule on the right.
                        </td>
                      </tr>
                    ) : (
                      schedules.map((sch) => (
                        <tr key={sch.id} className="hover:bg-zinc-50/50">
                          <td className="p-3 font-semibold text-zinc-900">{sch.name}</td>
                          <td className="p-3 font-mono capitalize">{sch.cron_expression}</td>
                          <td className="p-3">
                            <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase bg-teal-50 text-teal-700">
                              {sch.status}
                            </span>
                          </td>
                          <td className="p-3 text-zinc-500">{new Date(sch.next_run).toLocaleDateString()} {new Date(sch.next_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                          <td className="p-3 text-right">
                            <button
                              onClick={() => handleDeleteSchedule(sch.id)}
                              className="inline-flex items-center rounded border border-rose-200 bg-rose-50 hover:bg-rose-100 p-1 text-rose-600"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>

        {/* Right 1 Column: Action Forms depending on sub-tab */}
        <div className="space-y-6">
          
          {activeSubTab === "library" && (
            <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
                <Sliders className="h-4.5 w-4.5 text-zinc-500" />
                Report Builder (Custom Generation)
              </h3>
              
              <form onSubmit={handleGenerate} className="space-y-3.5 text-xs text-zinc-700">
                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Document Name</label>
                  <input
                    type="text"
                    value={reportName}
                    onChange={(e) => setReportName(e.target.value)}
                    placeholder="Q3 KYC Verification Audit Report"
                    className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Report Focus Type</label>
                  <select
                    value={reportType}
                    onChange={(e) => setReportType(e.target.value)}
                    className="w-full rounded border border-zinc-300 p-2 bg-white focus:outline-none focus:border-teal-500"
                  >
                    <option value="customer_summary">Customer Summary</option>
                    <option value="high_risk_customers">High Risk Customers</option>
                    <option value="risk_distribution">Risk Distribution</option>
                    <option value="transaction_summary">Transaction Summary</option>
                    <option value="suspicious_transactions">Suspicious Transactions</option>
                    <option value="case_statistics">Case Statistics</option>
                    <option value="alert_statistics">Alert Statistics</option>
                    <option value="sar_statistics">SAR Statistics</option>
                    <option value="investigation_statistics">Investigation Statistics</option>
                    <option value="monitoring_statistics">Monitoring Statistics</option>
                    <option value="regulation_compliance">Regulation Compliance</option>
                    <option value="policy_rule_activity">Policy Rule Activity</option>
                    <option value="agent_performance">Agent Performance</option>
                    <option value="dashboard_kpis">Dashboard KPIs</option>
                    <option value="audit_activity">Audit Activity</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Output Export Format</label>
                  <div className="flex gap-2">
                    {(["pdf", "excel", "csv", "json"] as const).map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => setReportFormat(fmt)}
                        className={`flex-1 py-1.5 rounded border text-center font-bold uppercase transition ${
                          reportFormat === fmt
                            ? "bg-teal-600 border-teal-600 text-white shadow-sm"
                            : "border-zinc-300 bg-white hover:bg-zinc-50 text-zinc-700"
                        }`}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Link Template (Optional)</label>
                  <select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    className="w-full rounded border border-zinc-300 p-2 bg-white focus:outline-none focus:border-teal-500"
                  >
                    <option value="">No template</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-2 rounded-lg mt-2 shadow-sm transition disabled:opacity-50"
                >
                  Generate Report
                </button>
              </form>
            </div>
          )}

          {activeSubTab === "templates" && (
            <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
                <Sliders className="h-4.5 w-4.5 text-zinc-500" />
                Create Template
              </h3>
              
              <form onSubmit={handleCreateTemplate} className="space-y-3.5 text-xs text-zinc-700">
                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Template Name</label>
                  <input
                    type="text"
                    value={tmplName}
                    onChange={(e) => setTmplName(e.target.value)}
                    placeholder="Weekly Sanctions Hit template"
                    className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Description</label>
                  <textarea
                    value={tmplDesc}
                    onChange={(e) => setTmplDesc(e.target.value)}
                    placeholder="Default filters for high-risk audits description details..."
                    className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                    rows={2}
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Report Focus Type</label>
                  <select
                    value={tmplReportType}
                    onChange={(e) => setTmplReportType(e.target.value)}
                    className="w-full rounded border border-zinc-300 p-2 bg-white focus:outline-none focus:border-teal-500"
                  >
                    <option value="customer_summary">Customer Summary</option>
                    <option value="high_risk_customers">High Risk Customers</option>
                    <option value="transaction_summary">Transaction Summary</option>
                    <option value="suspicious_transactions">Suspicious Transactions</option>
                    <option value="case_statistics">Case Statistics</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Default Output Format</label>
                  <select
                    value={tmplFormat}
                    onChange={(e) => setTmplFormat(e.target.value)}
                    className="w-full rounded border border-zinc-300 p-2 bg-white focus:outline-none focus:border-teal-500"
                  >
                    <option value="pdf">PDF</option>
                    <option value="excel">Excel (.xlsx)</option>
                    <option value="csv">CSV</option>
                    <option value="json">JSON</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-2 rounded-lg mt-2 shadow-sm transition disabled:opacity-50"
                >
                  Save Template
                </button>
              </form>
            </div>
          )}

          {activeSubTab === "schedules" && (
            <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-zinc-900 text-sm flex items-center gap-1.5">
                <Calendar className="h-4.5 w-4.5 text-zinc-500" />
                Create Scheduled Cron
              </h3>
              
              <form onSubmit={handleCreateSchedule} className="space-y-3.5 text-xs text-zinc-700">
                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Schedule Name</label>
                  <input
                    type="text"
                    value={schedName}
                    onChange={(e) => setSchedName(e.target.value)}
                    placeholder="Weekly AML audit scan"
                    className="w-full rounded border border-zinc-300 p-2 focus:outline-none focus:border-teal-500"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Source Report Template</label>
                  <select
                    value={schedTmplId}
                    onChange={(e) => setSchedTmplId(e.target.value)}
                    className="w-full rounded border border-zinc-300 p-2 bg-white focus:outline-none focus:border-teal-500"
                    required
                  >
                    <option value="">Choose template...</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-zinc-600">Frequency Interval</label>
                  <select
                    value={schedCron}
                    onChange={(e) => setSchedCron(e.target.value)}
                    className="w-full rounded border border-zinc-300 p-2 bg-white focus:outline-none focus:border-teal-500"
                  >
                    <option value="daily">Daily execution</option>
                    <option value="weekly">Weekly execution</option>
                    <option value="monthly">Monthly execution</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={loading || templates.length === 0}
                  className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-2 rounded-lg mt-2 shadow-sm transition disabled:opacity-50"
                >
                  Schedule Report Cron
                </button>
              </form>
            </div>
          )}

        </div>

      </div>
    </div>
  );
}
