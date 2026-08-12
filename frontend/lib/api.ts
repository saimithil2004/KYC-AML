export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// Re-export types from the central types file for backward compat
export type {
  User,
  AuthResponse,
  Customer,
  KycProfile,
  DocumentRecord,
  RiskScore,
  Case,
  DocumentOcrResponse,
  RegulationVersion,
  MonitoringSchedule,
  MonitoringHistory,
  MonitoringJob,
  MonitoringStatistics,
  RiskDelta,
  Investigation,
  Evidence,
  CaseNote,
  SAR,
  TimelineEvent,
  Assignment,
  InvestigatorWorkload,
  InvestigationDashboardMetrics,
  InvestigationWorkspacePayload,
  ReportTemplate,
  Report,
  ScheduledReport,
  ReportExecution,
  DashboardWidget,
  DashboardLayout,
  PeriodicKPIs,
  FullObservabilityReport,
  BackupRecord,
  LoginHistoryEntry,
  MFAEnrollData,
  MFASetupResponse,
  SystemHealthDetails,
  DevOpsStatusReport,
  AIModel,
  PromptTemplate,
  PromptVersion,
  AIExecution,
  AIExplanation,
  AIFeedback,
  ModelEvaluation,
  AIPolicy,
  AIStatistics,
  AIUsage,
} from "./types";

import type {
  FullObservabilityReport,
  BackupRecord,
  LoginHistoryEntry,
  MFAEnrollData,
  MFASetupResponse,
  SystemHealthDetails,
  DevOpsStatusReport,
  AIModel,
  PromptTemplate,
  PromptVersion,
  AIExecution,
  AIExplanation,
  AIFeedback,
  ModelEvaluation,
  AIPolicy,
  AIStatistics,
  AIUsage,
} from "./types";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_profile");
      if (!window.location.pathname.startsWith("/auth/")) {
        window.location.href = "/auth/login?session_expired=true";
      }
    }
    const errorText = await response.text().catch(() => "");
    let payload: Record<string, any> = {};
    if (errorText && errorText.trim()) {
      try {
        payload = JSON.parse(errorText);
      } catch {
        payload = {};
      }
    }
    throw new Error(payload.detail || payload.message || errorText || `Request failed (${response.status})`);
  }

  // HTTP 204 No Content or 205 Reset Content have no response body
  if (response.status === 204 || response.status === 205) {
    return {} as T;
  }

  const text = await response.text();
  if (!text || !text.trim()) {
    return {} as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (err) {
    return {} as T;
  }
}


export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  return parseResponse<T>(response);
}

// ─── Customer API ─────────────────────────────────────────────────────────────
import type { Customer, KycProfile, DocumentRecord, RiskScore } from "./types";

export async function ensureCustomer(token: string): Promise<Customer> {
  try {
    return await apiRequest<Customer>("/customers/me", {}, token);
  } catch {
    return apiRequest<Customer>(
      "/customers/",
      { method: "POST", body: JSON.stringify({ customer_type: "individual" }) },
      token
    );
  }
}

export async function updateCustomer(
  customerId: string,
  data: Partial<Customer>,
  token: string
): Promise<Customer> {
  return apiRequest<Customer>(
    `/customers/${customerId}`,
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

// ─── KYC API ─────────────────────────────────────────────────────────────────
export async function getKycProfile(
  customerId: string,
  token: string
): Promise<KycProfile> {
  return apiRequest<KycProfile>(`/kyc/${customerId}`, {}, token);
}

export async function createKycProfile(
  data: Record<string, unknown>,
  token: string
): Promise<KycProfile> {
  return apiRequest<KycProfile>(
    "/kyc/",
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export async function updateKycProfile(
  customerId: string,
  data: Record<string, unknown>,
  token: string
): Promise<KycProfile> {
  return apiRequest<KycProfile>(
    `/kyc/${customerId}`,
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

// ─── Documents API ───────────────────────────────────────────────────────────
export async function getCustomerDocuments(
  customerId: string,
  token: string
): Promise<DocumentRecord[]> {
  return apiRequest<DocumentRecord[]>(
    `/documents/customer/${customerId}`,
    {},
    token
  );
}

export async function uploadDocument(
  customerId: string,
  documentType: string,
  file: File,
  token: string,
  onProgress?: (pct: number) => void
): Promise<DocumentRecord> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("customer_id", customerId);
    formData.append("document_type", documentType);
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/documents/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as DocumentRecord);
        } catch {
          reject(new Error("Invalid response format"));
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || "Upload failed"));
        } catch {
          reject(new Error("Upload failed"));
        }
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}

export async function getDocumentOcrData(
  documentId: string,
  token: string
): Promise<{
  document_id: string;
  verification_status: string;
  ocr_data: Record<string, any> | null;
  // The backend returns "metadata", NOT "verification_metadata"
  metadata: Record<string, unknown>;
  validation: Record<string, unknown> | null;
  matching: Record<string, unknown> | null;
  risk: Record<string, unknown> | null;
  history: Record<string, unknown>[];
}> {
  return apiRequest(`/documents/${documentId}`, {}, token);
}

export async function verifyDocumentOcr(
  documentId: string,
  ocrData: Record<string, any>,
  token: string
): Promise<any> {
  return apiRequest(
    "/documents/verify",
    {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        ocr_data: ocrData,
      }),
    },
    token
  );
}

export async function deleteDocument(
  documentId: string,
  token: string
): Promise<void> {
  return apiRequest(`/documents/${documentId}`, { method: "DELETE" }, token);
}

export async function reprocessDocument(
  documentId: string,
  token: string
): Promise<any> {
  return apiRequest(`/documents/${documentId}/reprocess`, { method: "POST" }, token);
}


// ─── Risk Score API ───────────────────────────────────────────────────────────
export async function getLatestRiskScore(
  customerId: string,
  token: string
): Promise<RiskScore | null> {
  try {
    const scores = await apiRequest<RiskScore[]>(
      `/risk-scores/customer/${customerId}`,
      {},
      token
    );
    return scores.length > 0 ? scores[0] : null;
  } catch {
    return null;
  }
}

// ─── Phase 8: Transactions API ────────────────────────────────────────────────
import type { Transaction, Alert, Case as CaseType, AuditLog, Paginated, RescreeningResult, FullCase } from "./types";

export async function listTransactions(
  token: string,
  params?: {
    page?: number; page_size?: number; customer_id?: string;
    status?: string; transaction_type?: string; date_from?: string;
    date_to?: string; search?: string; sort_by?: string; sort_dir?: string;
  }
): Promise<Paginated<Transaction>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<Transaction>>(`/transactions/?${qs}`, {}, token);
}

export async function getTransaction(id: string, token: string): Promise<Transaction> {
  return apiRequest<Transaction>(`/transactions/${id}`, {}, token);
}

export async function createTransaction(data: Record<string, unknown>, token: string): Promise<Transaction> {
  return apiRequest<Transaction>("/transactions/", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function importTransactionsCsv(file: File, token: string): Promise<{ imported: number; errors_count: number; alerts_generated: number; message: string }> {
  const fd = new FormData();
  fd.append("file", file);
  return apiRequest("/transactions/import", { method: "POST", body: fd }, token);
}

export async function updateTransaction(id: string, data: Record<string, unknown>, token: string): Promise<Transaction> {
  return apiRequest<Transaction>(`/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) }, token);
}

export async function deleteTransaction(id: string, token: string): Promise<void> {
  return apiRequest(`/transactions/${id}`, { method: "DELETE" }, token);
}

export async function getCustomerTransactions(customerId: string, token: string, page = 1): Promise<Paginated<Transaction>> {
  return apiRequest<Paginated<Transaction>>(`/transactions/customer/${customerId}?page=${page}&page_size=20`, {}, token);
}

// ─── Phase 8: Alerts API ──────────────────────────────────────────────────────

export async function listAlerts(
  token: string,
  params?: {
    page?: number; page_size?: number; customer_id?: string;
    status?: string; alert_type?: string; sort_dir?: string;
  }
): Promise<Paginated<Alert>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<Alert>>(`/alerts/?${qs}`, {}, token);
}

export async function getAlert(id: string, token: string): Promise<Alert> {
  return apiRequest<Alert>(`/alerts/${id}`, {}, token);
}

export async function updateAlert(id: string, data: { status?: string; alert_metadata?: Record<string, unknown> }, token: string): Promise<Alert> {
  return apiRequest<Alert>(`/alerts/${id}`, { method: "PUT", body: JSON.stringify(data) }, token);
}

export async function createAlert(data: Record<string, unknown>, token: string): Promise<Alert> {
  return apiRequest<Alert>("/alerts/", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function getCustomerAlerts(customerId: string, token: string): Promise<Paginated<Alert>> {
  return apiRequest<Paginated<Alert>>(`/alerts/customer/${customerId}`, {}, token);
}

// ─── Phase 8: Cases API ───────────────────────────────────────────────────────

export async function listCases(
  token: string,
  params?: {
    page?: number; page_size?: number; customer_id?: string;
    status?: string; priority?: string; sort_dir?: string;
  }
): Promise<Paginated<CaseType>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<CaseType>>(`/cases/?${qs}`, {}, token);
}

export async function getCase(id: string, token: string): Promise<CaseType> {
  return apiRequest<CaseType>(`/cases/${id}`, {}, token);
}

export async function getCaseFull(id: string, token: string): Promise<FullCase> {
  return apiRequest<FullCase>(`/cases/${id}/full`, {}, token);
}

export async function createCase(data: Record<string, unknown>, token: string): Promise<CaseType> {
  return apiRequest<CaseType>("/cases/", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function updateCase(id: string, data: Record<string, unknown>, token: string): Promise<CaseType> {
  return apiRequest<CaseType>(`/cases/${id}`, { method: "PUT", body: JSON.stringify(data) }, token);
}

export async function submitCaseDecision(id: string, data: { decision: string; notes: string; reason?: string; sar_filed?: boolean }, token: string): Promise<CaseType> {
  return apiRequest<CaseType>(`/cases/${id}/decision`, { method: "POST", body: JSON.stringify(data) }, token);
}

// ─── Phase 8: Screening API ───────────────────────────────────────────────────

export async function runScreening(customerId: string, token: string): Promise<RescreeningResult> {
  return apiRequest<RescreeningResult>(`/screening/${customerId}/run`, { method: "POST" }, token);
}

export async function getScreeningStatus(customerId: string, token: string): Promise<unknown> {
  return apiRequest(`/screening/${customerId}/status`, {}, token);
}

// ─── Phase 8: Audit Logs API ──────────────────────────────────────────────────

export async function listAuditLogs(token: string, params?: { page?: number; entity_name?: string; action?: string }): Promise<Paginated<AuditLog>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<AuditLog>>(`/audit-logs/?${qs}`, {}, token);
}

// ─── Phase 9: Dashboard API ───────────────────────────────────────────────────

export async function getDashboardOverview(token: string): Promise<any> {
  return apiRequest<any>("/dashboard/overview", {}, token);
}

export async function getDashboardCharts(token: string): Promise<any> {
  return apiRequest<any>("/dashboard/charts", {}, token);
}

export async function getDashboardActivity(token: string, limit = 30): Promise<any[]> {
  return apiRequest<any[]>(`/dashboard/activity?limit=${limit}`, {}, token);
}

export async function getDashboardRisk(token: string, limit = 10): Promise<any[]> {
  return apiRequest<any[]>(`/dashboard/risk?limit=${limit}`, {}, token);
}

export async function getDashboardAlerts(token: string): Promise<any> {
  return apiRequest<any>("/dashboard/alerts", {}, token);
}

export async function getDashboardCases(token: string): Promise<any> {
  return apiRequest<any>("/dashboard/cases", {}, token);
}

export async function getDashboardMonitoring(token: string): Promise<any> {
  return apiRequest<any>("/dashboard/monitoring", {}, token);
}

export async function getDashboardAI(token: string): Promise<any> {
  return apiRequest<any>("/dashboard/ai", {}, token);
}

export async function searchDashboard(token: string, query: string): Promise<any> {
  return apiRequest<any>(`/dashboard/search?q=${encodeURIComponent(query)}`, {}, token);
}

// ─── Phase 10: Regulations & Policy API ───────────────────────────────────────
import type { Regulation, PolicyRule, RegulationVersion, MonitoringSchedule, MonitoringHistory, MonitoringJob, MonitoringStatistics, RiskDelta, Investigation, Evidence, CaseNote, SAR, TimelineEvent, Assignment, InvestigatorWorkload, InvestigationDashboardMetrics, InvestigationWorkspacePayload, ReportTemplate, Report, ScheduledReport, ReportExecution, DashboardWidget, DashboardLayout, PeriodicKPIs } from "./types";

export async function listRegulations(
  token: string,
  params?: { page?: number; page_size?: number; search?: string; country?: string; status?: string }
): Promise<Paginated<Regulation>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<Regulation>>(`/regulations/?${qs}`, {}, token);
}

export async function uploadRegulation(token: string, formData: FormData): Promise<Regulation> {
  // Let the browser handle Content-Type boundary for multipart/form-data
  return apiRequest<Regulation>("/regulations/", {
    method: "POST",
    body: formData,
  }, token);
}

export async function getRegulation(id: string, token: string): Promise<Regulation> {
  return apiRequest<Regulation>(`/regulations/${id}`, {}, token);
}

export async function updateRegulation(id: string, data: Record<string, unknown>, token: string): Promise<Regulation> {
  return apiRequest<Regulation>(`/regulations/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  }, token);
}

export async function deleteRegulation(id: string, token: string): Promise<void> {
  return apiRequest(`/regulations/${id}`, { method: "DELETE" }, token);
}

export async function extractRulesFromRegulation(id: string, token: string): Promise<PolicyRule[]> {
  return apiRequest<PolicyRule[]>(`/regulations/${id}/extract-rules`, { method: "POST" }, token);
}

export async function listPolicyRules(
  token: string,
  params?: { page?: number; page_size?: number; rule_type?: string; is_active?: boolean; country?: string }
): Promise<Paginated<PolicyRule>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<PolicyRule>>(`/policy-rules/?${qs}`, {}, token);
}

export async function createPolicyRule(data: Record<string, unknown>, token: string): Promise<PolicyRule> {
  return apiRequest<PolicyRule>("/policy-rules/", {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

export async function updatePolicyRule(id: string, data: Record<string, unknown>, token: string): Promise<PolicyRule> {
  return apiRequest<PolicyRule>(`/policy-rules/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  }, token);
}

export async function deletePolicyRule(id: string, token: string): Promise<void> {
  return apiRequest(`/policy-rules/${id}`, { method: "DELETE" }, token);
}

export async function listRegulationVersions(id: string, token: string): Promise<RegulationVersion[]> {
  return apiRequest<RegulationVersion[]>(`/regulations/${id}/versions`, {}, token);
}

export async function rollbackRegulation(id: string, versionId: string, reason: string, token: string): Promise<Regulation> {
  return apiRequest<Regulation>(`/regulations/${id}/rollback`, {
    method: "POST",
    body: JSON.stringify({ version_id: versionId, reason }),
  }, token);
}

// ─── Phase 11: Continuous Monitoring API ────────────────────────────────────

export async function listMonitoringSchedules(
  token: string,
  params?: { page?: number; page_size?: number; status?: string }
): Promise<Paginated<MonitoringSchedule>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<MonitoringSchedule>>(`/monitoring/?${qs}`, {}, token);
}

export async function listMonitoringHistory(
  token: string,
  params?: { page?: number; page_size?: number; customer_id?: string }
): Promise<Paginated<MonitoringHistory>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<MonitoringHistory>>(`/monitoring/history?${qs}`, {}, token);
}

export async function listMonitoringJobs(
  token: string,
  params?: { page?: number; page_size?: number; status?: string }
): Promise<Paginated<MonitoringJob>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<MonitoringJob>>(`/monitoring/jobs?${qs}`, {}, token);
}

export async function triggerManualRescreen(customerId: string, token: string): Promise<MonitoringJob> {
  return apiRequest<MonitoringJob>(`/monitoring/run/${customerId}`, { method: "POST" }, token);
}

export async function retryFailedJob(jobId: string, token: string): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>(`/monitoring/retry/${jobId}`, { method: "POST" }, token);
}

export async function cancelJob(jobId: string, token: string): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>(`/monitoring/cancel/${jobId}`, { method: "POST" }, token);
}

export async function listPendingReviews(
  token: string,
  params?: { page?: number; page_size?: number }
): Promise<Paginated<MonitoringSchedule>> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)); });
  }
  return apiRequest<Paginated<MonitoringSchedule>>(`/monitoring/reviews?${qs}`, {}, token);
}

export async function getMonitoringStatistics(token: string): Promise<MonitoringStatistics> {
  return apiRequest<MonitoringStatistics>("/monitoring/statistics", {}, token);
}

export async function getCustomerRiskDelta(customerId: string, token: string): Promise<RiskDelta> {
  return apiRequest<RiskDelta>(`/monitoring/risk-delta/${customerId}`, {}, token);
}


// ─── Phase 12: Investigations API ───────────────────────────────────────────

export async function listInvestigations(
  token: string,
  params?: { page?: number; page_size?: number; status?: string; risk_level?: string }
): Promise<Paginated<Investigation>> {
  const qs = new URLSearchParams();
  if (params) {
    if (params.page !== undefined) qs.set("page", String(params.page));
    if (params.page_size !== undefined) qs.set("page_size", String(params.page_size));
    if (params.status !== undefined) qs.set("status_filter", String(params.status));
    if (params.risk_level !== undefined) qs.set("risk_filter", String(params.risk_level));
  }
  return apiRequest<Paginated<Investigation>>(`/investigations/?${qs}`, {}, token);
}

export async function getInvestigationDashboard(token: string): Promise<InvestigationDashboardMetrics> {
  return apiRequest<InvestigationDashboardMetrics>("/investigations/dashboard", {}, token);
}

export async function getInvestigationWorkspace(id: string, token: string): Promise<InvestigationWorkspacePayload> {
  return apiRequest<InvestigationWorkspacePayload>(`/investigations/${id}`, {}, token);
}

export async function updateInvestigation(
  id: string,
  data: { status?: string; risk_level?: string },
  token: string
): Promise<Investigation> {
  const formData = new FormData();
  if (data.status) formData.append("status", data.status);
  if (data.risk_level) formData.append("risk_level", data.risk_level);

  return apiRequest<Investigation>(`/investigations/${id}`, {
    method: "PUT",
    body: formData,
  }, token);
}

export async function assignInvestigation(
  id: string,
  data: { assigned_to: string; role: "investigator" | "supervisor" },
  token: string
): Promise<Assignment> {
  return apiRequest<Assignment>(`/investigations/${id}/assign`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

export async function addCaseNote(id: string, data: { note_text: string }, token: string): Promise<CaseNote> {
  return apiRequest<CaseNote>(`/investigations/${id}/note`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

export async function updateCaseNote(id: string, noteId: string, data: { note_text: string }, token: string): Promise<CaseNote> {
  return apiRequest<CaseNote>(`/investigations/${id}/note/${noteId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  }, token);
}

export async function deleteCaseNote(id: string, noteId: string, token: string): Promise<void> {
  return apiRequest<void>(`/investigations/${id}/note/${noteId}`, { method: "DELETE" }, token);
}

export async function uploadEvidenceFile(
  id: string,
  file: File,
  description: string | null,
  token: string
): Promise<Evidence> {
  const formData = new FormData();
  formData.append("file", file);
  if (description) {
    formData.append("description", description);
  }
  return apiRequest<Evidence>(`/investigations/${id}/evidence`, {
    method: "POST",
    body: formData,
  }, token);
}

export async function deleteEvidenceFile(id: string, evidenceId: string, token: string): Promise<void> {
  return apiRequest<void>(`/investigations/${id}/evidence/${evidenceId}`, { method: "DELETE" }, token);
}

export async function getTimeline(id: string, token: string): Promise<TimelineEvent[]> {
  return apiRequest<TimelineEvent[]>(`/investigations/${id}/timeline`, {}, token);
}

export async function generateSarDraft(
  id: string,
  data: { narrative: string; reason: string; risk_indicators: string[]; recommendation: string },
  token: string
): Promise<SAR> {
  return apiRequest<SAR>(`/investigations/${id}/sar`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

export async function getSars(id: string, token: string): Promise<SAR[]> {
  return apiRequest<SAR[]>(`/investigations/${id}/sar`, {}, token);
}

export async function updateSarStatus(id: string, data: { status: string }, token: string): Promise<SAR> {
  return apiRequest<SAR>(`/investigations/${id}/sar`, {
    method: "PUT",
    body: JSON.stringify(data),
  }, token);
}

export async function closeInvestigation(id: string, token: string): Promise<Investigation> {
  return apiRequest<Investigation>(`/investigations/${id}/close`, { method: "POST" }, token);
}

export async function reopenInvestigation(id: string, token: string): Promise<Investigation> {
  return apiRequest<Investigation>(`/investigations/${id}/reopen`, { method: "POST" }, token);
}

export async function escalateInvestigation(id: string, data: { action: string }, token: string): Promise<Investigation> {
  return apiRequest<Investigation>(`/investigations/${id}/escalate`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}


// ─── Phase 13: Reporting & BI API ────────────────────────────────────────────

export async function listReports(token: string, params?: { page?: number; page_size?: number }): Promise<Report[]> {
  const qs = new URLSearchParams();
  if (params) {
    if (params.page !== undefined) qs.set("page", String(params.page));
    if (params.page_size !== undefined) qs.set("page_size", String(params.page_size));
  }
  return apiRequest<Report[]>(`/reports/?${qs}`, {}, token);
}

export async function generateReport(token: string, data: { name: string; format: string; filters: Record<string, any> }): Promise<Report> {
  return apiRequest<Report>("/reports/generate", {
    method: "POST",
    body: JSON.stringify(data)
  }, token);
}

export async function getReportDetails(id: string, token: string): Promise<Report> {
  return apiRequest<Report>(`/reports/${id}`, {}, token);
}

export async function deleteReport(id: string, token: string): Promise<void> {
  return apiRequest<void>(`/reports/${id}`, { method: "DELETE" }, token);
}

export async function listReportTemplates(token: string): Promise<ReportTemplate[]> {
  return apiRequest<ReportTemplate[]>("/reports/templates", {}, token);
}

export async function createReportTemplate(token: string, data: { name: string; description?: string; config: Record<string, any> }): Promise<ReportTemplate> {
  return apiRequest<ReportTemplate>("/reports/templates", {
    method: "POST",
    body: JSON.stringify(data)
  }, token);
}

export async function updateReportTemplate(id: string, token: string, data: { name: string; description?: string; config: Record<string, any> }): Promise<ReportTemplate> {
  return apiRequest<ReportTemplate>(`/reports/templates/${id}`, {
    method: "PUT",
    body: JSON.stringify(data)
  }, token);
}

export async function deleteReportTemplate(id: string, token: string): Promise<void> {
  return apiRequest<void>(`/reports/templates/${id}`, { method: "DELETE" }, token);
}

export async function listReportSchedules(token: string): Promise<ScheduledReport[]> {
  return apiRequest<ScheduledReport[]>("/reports/schedules", {}, token);
}

export async function createReportSchedule(token: string, data: { name: string; template_id: string; cron_expression: string }): Promise<ScheduledReport> {
  return apiRequest<ScheduledReport>("/reports/schedules", {
    method: "POST",
    body: JSON.stringify(data)
  }, token);
}

export async function updateReportSchedule(id: string, token: string, data: { status?: string; cron_expression?: string }): Promise<ScheduledReport> {
  return apiRequest<ScheduledReport>(`/reports/schedules/${id}`, {
    method: "PUT",
    body: JSON.stringify(data)
  }, token);
}

export async function deleteReportSchedule(id: string, token: string): Promise<void> {
  return apiRequest<void>(`/reports/schedules/${id}`, { method: "DELETE" }, token);
}

export async function getAnalyticsKPIs(token: string, period: string = "monthly"): Promise<PeriodicKPIs> {
  return apiRequest<PeriodicKPIs>(`/analytics/?period=${period}`, {}, token);
}

export async function getAnalyticsDashboard(token: string): Promise<PeriodicKPIs> {
  return apiRequest<PeriodicKPIs>("/analytics/dashboard", {}, token);
}

export async function getAnalyticsRisk(token: string): Promise<any> {
  return apiRequest<any>("/analytics/risk", {}, token);
}

export async function getAnalyticsCases(token: string): Promise<any> {
  return apiRequest<any>("/analytics/cases", {}, token);
}

export async function getAnalyticsInvestigations(token: string): Promise<any> {
  return apiRequest<any>("/analytics/investigations", {}, token);
}

export async function getAnalyticsTransactions(token: string): Promise<any> {
  return apiRequest<any>("/analytics/transactions", {}, token);
}


// ─── PHASE 14 — External Integrations & Notifications ────────────────────────

export async function getIntegrationSettings(token: string) {
  return apiRequest<any[]>("/integrations/settings", {}, token);
}
export async function createIntegrationSetting(token: string, data: any) {
  return apiRequest<any>("/integrations/settings", { method: "POST", body: JSON.stringify(data) }, token);
}
export async function updateIntegrationSetting(token: string, id: string, data: any) {
  return apiRequest<any>(`/integrations/settings/${id}`, { method: "PUT", body: JSON.stringify(data) }, token);
}
export async function deleteIntegrationSetting(token: string, id: string) {
  return apiRequest<any>(`/integrations/settings/${id}`, { method: "DELETE" }, token);
}
export async function triggerManualSync(token: string, provider: string) {
  return apiRequest<any>("/integrations/sync/manual", { method: "POST", body: JSON.stringify({ provider, sync_type: "manual" }) }, token);
}
export async function triggerSyncAll(token: string) {
  return apiRequest<any>("/integrations/sync/all", { method: "POST" }, token);
}
export async function getSyncStatus(token: string, provider?: string) {
  const qs = provider ? `?provider=${provider}` : "";
  return apiRequest<any[]>(`/integrations/sync/status${qs}`, {}, token);
}
export async function getProviderHealth(token: string) {
  return apiRequest<any[]>("/integrations/health/providers", {}, token);
}
export async function getProviderVersions(token: string) {
  return apiRequest<any[]>("/integrations/providers/versions", {}, token);
}
export async function getNotificationTemplates(token: string, event_type?: string, channel?: string) {
  const params = new URLSearchParams();
  if (event_type) params.set("event_type", event_type);
  if (channel) params.set("channel", channel);
  const qs = params.toString() ? `?${params}` : "";
  return apiRequest<any[]>(`/integrations/notification-templates${qs}`, {}, token);
}
export async function createNotificationTemplate(token: string, data: any) {
  return apiRequest<any>("/integrations/notification-templates", { method: "POST", body: JSON.stringify(data) }, token);
}
export async function updateNotificationTemplate(token: string, id: string, data: any) {
  return apiRequest<any>(`/integrations/notification-templates/${id}`, { method: "PUT", body: JSON.stringify(data) }, token);
}
export async function deleteNotificationTemplate(token: string, id: string) {
  return apiRequest<any>(`/integrations/notification-templates/${id}`, { method: "DELETE" }, token);
}
export async function getNotificationHistory(token: string, channel?: string, status?: string) {
  const params = new URLSearchParams();
  if (channel) params.set("channel", channel);
  if (status) params.set("status", status);
  const qs = params.toString() ? `?${params}` : "";
  return apiRequest<any[]>(`/integrations/notifications/history${qs}`, {}, token);
}
export async function sendNotification(token: string, data: any) {
  return apiRequest<any>("/integrations/notifications/send", { method: "POST", body: JSON.stringify(data) }, token);
}
export async function getUnreadNotificationCount(token: string) {
  return apiRequest<{ unread_count: number }>("/integrations/notifications/unread-count", {}, token);
}
export async function getWebhooks(token: string) {
  return apiRequest<any[]>("/integrations/webhooks", {}, token);
}
export async function createWebhook(token: string, data: any) {
  return apiRequest<any>("/integrations/webhooks", { method: "POST", body: JSON.stringify(data) }, token);
}
export async function updateWebhook(token: string, id: string, data: any) {
  return apiRequest<any>(`/integrations/webhooks/${id}`, { method: "PUT", body: JSON.stringify(data) }, token);
}
export async function deleteWebhook(token: string, id: string) {
  return apiRequest<any>(`/integrations/webhooks/${id}`, { method: "DELETE" }, token);
}
export async function testWebhook(token: string, id: string) {
  return apiRequest<any>(`/integrations/webhooks/${id}/test`, { method: "POST" }, token);
}
export async function getWebhookLogs(token: string, id: string) {
  return apiRequest<any[]>(`/integrations/webhooks/${id}/logs`, {}, token);
}
export async function getAllWebhookLogs(token: string, event?: string) {
  const qs = event ? `?event=${event}` : "";
  return apiRequest<any[]>(`/integrations/webhooks/logs/all${qs}`, {}, token);
}
export async function getWebhookEvents(token: string) {
  return apiRequest<{ events: string[] }>("/integrations/webhooks/events/list", {}, token);
}

// ─── Phase 15: Enterprise Hardening, Observability & Backups ──────────────────

export async function getHealth(): Promise<{ status: string; latency_ms: number; version: string; timestamp: string }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error("Health check request failed");
  return res.json();
}

export async function getFullHealth(token: string): Promise<FullObservabilityReport> {
  return apiRequest<FullObservabilityReport>("/health/full", {}, token);
}

export async function getSystemHealth(token: string): Promise<{ status: string; details: SystemHealthDetails }> {
  return apiRequest<{ status: string; details: SystemHealthDetails }>("/health/system", {}, token);
}

export async function listBackups(token: string): Promise<BackupRecord[]> {
  return apiRequest<BackupRecord[]>("/system/backups", {}, token);
}

export async function triggerBackup(token: string, type: "database" | "documents" | "config" | "full" = "database"): Promise<BackupRecord> {
  return apiRequest<BackupRecord>(`/system/backups?backup_type=${type}`, { method: "POST" }, token);
}

export async function verifyBackup(token: string, id: string): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>(`/system/backups/${id}/verify`, { method: "POST" }, token);
}

export async function deleteBackup(token: string, id: string): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>(`/system/backups/${id}`, { method: "DELETE" }, token);
}

export async function getMetricsHistory(token: string, metricName: string = "cpu_percent"): Promise<any[]> {
  return apiRequest<any[]>(`/system/metrics/history?metric_name=${metricName}`, {}, token);
}

export async function getLoginHistory(token: string): Promise<LoginHistoryEntry[]> {
  return apiRequest<LoginHistoryEntry[]>("/auth/login-history", {}, token);
}

export async function changePassword(token: string, data: any): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>("/auth/change-password", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function enrollMfa(token: string): Promise<MFAEnrollData> {
  return apiRequest<MFAEnrollData>("/auth/mfa/setup", { method: "POST" }, token);
}

export async function verifyMfa(token: string, code: string): Promise<MFASetupResponse> {
  return apiRequest<MFASetupResponse>("/auth/mfa/verify", { method: "POST", body: JSON.stringify({ code }) }, token);
}

export async function disableMfa(token: string): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>("/auth/mfa/disable", { method: "POST" }, token);
}

export async function getDevOpsStatus(token: string): Promise<DevOpsStatusReport> {
  return apiRequest<DevOpsStatusReport>("/devops/status", {}, token);
}

// ─── Phase 17: AI Governance API Mappings ────────────────────────────────────

export async function getAIModels(token: string): Promise<AIModel[]> {
  return apiRequest<AIModel[]>("/ai/models", {}, token);
}

export async function createAIModel(token: string, data: any): Promise<AIModel> {
  return apiRequest<AIModel>("/ai/models", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function createModelVersion(token: string, modelId: string, data: any): Promise<any> {
  return apiRequest<any>(`/ai/models/${modelId}/versions`, { method: "POST", body: JSON.stringify(data) }, token);
}

export async function updateAIModel(token: string, modelId: string, data: any): Promise<AIModel> {
  return apiRequest<AIModel>(`/ai/models/${modelId}`, { method: "PUT", body: JSON.stringify(data) }, token);
}

export async function deleteAIModel(token: string, modelId: string): Promise<any> {
  return apiRequest<any>(`/ai/models/${modelId}`, { method: "DELETE" }, token);
}

export async function getAIPrompts(token: string): Promise<PromptTemplate[]> {
  return apiRequest<PromptTemplate[]>("/ai/prompts", {}, token);
}

export async function createPromptTemplate(token: string, data: any): Promise<PromptTemplate> {
  return apiRequest<PromptTemplate>("/ai/prompts", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function createPromptVersion(token: string, templateId: string, data: any): Promise<PromptVersion> {
  return apiRequest<PromptVersion>(`/ai/prompts/${templateId}/versions`, { method: "POST", body: JSON.stringify(data) }, token);
}

export async function deletePromptTemplate(token: string, templateId: string): Promise<any> {
  return apiRequest<any>(`/ai/prompts/${templateId}`, { method: "DELETE" }, token);
}

export async function getAIExecutions(
  token: string,
  page: number = 1,
  limit: number = 20,
  customerId?: string
): Promise<{ total: number; page: number; limit: number; results: AIExecution[] }> {
  let url = `/ai/executions?page=${page}&limit=${limit}`;
  if (customerId) url += `&customer_id=${customerId}`;
  return apiRequest<any>(url, {}, token);
}

export async function getAIExecutionDetail(token: string, executionId: string): Promise<AIExecution> {
  return apiRequest<AIExecution>(`/ai/executions/${executionId}`, {}, token);
}

export async function getAIExplanation(token: string, executionId: string): Promise<AIExplanation> {
  return apiRequest<AIExplanation>(`/ai/explanations/${executionId}`, {}, token);
}

export async function submitAIFeedback(token: string, data: any): Promise<AIFeedback> {
  return apiRequest<AIFeedback>("/ai/feedback", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function approvePromptVersion(token: string, data: any): Promise<any> {
  return apiRequest<any>("/ai/approve", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function rejectPromptVersion(token: string, data: any): Promise<any> {
  return apiRequest<any>("/ai/reject", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function rollbackPromptVersion(token: string, data: any): Promise<any> {
  return apiRequest<any>("/ai/rollback", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function getAIPolicies(token: string): Promise<AIPolicy[]> {
  return apiRequest<AIPolicy[]>("/ai/policies", {}, token);
}

export async function createAIPolicy(token: string, data: any): Promise<AIPolicy> {
  return apiRequest<AIPolicy>("/ai/policies", { method: "POST", body: JSON.stringify(data) }, token);
}

export async function getAIUsageStats(token: string): Promise<{ results: AIUsage[] }> {
  return apiRequest<{ results: AIUsage[] }>("/ai/statistics", {}, token);
}

export async function getAIDashboardMetrics(token: string): Promise<AIStatistics> {
  return apiRequest<AIStatistics>("/ai/dashboard", {}, token);
}

export async function getAIProviderStatus(token: string): Promise<{ providers: any[] }> {
  return apiRequest<any>("/ai/provider-status", {}, token);
}

export async function getModelEvaluations(token: string): Promise<ModelEvaluation[]> {
  return apiRequest<ModelEvaluation[]>("/ai/evaluations", {}, token);
}

export async function submitModelEvaluation(token: string, data: any): Promise<any> {
  return apiRequest<any>("/ai/evaluate", { method: "POST", body: JSON.stringify(data) }, token);
}




