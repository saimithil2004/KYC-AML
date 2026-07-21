import { z } from "zod";

// ─── Enums ───────────────────────────────────────────────────────────────────
export const CUSTOMER_TYPES = ["individual", "corporate"] as const;
export const RISK_CATEGORIES = ["low", "medium", "high"] as const;
export const DOCUMENT_TYPES = [
  "passport",
  "national_id",
  "driving_licence",
  "proof_of_address",
  "company_document",
  "bank_statement",
  "utility_bill",
] as const;

export const SOURCE_OF_FUNDS_OPTIONS = [
  "Salary / Employment",
  "Business Income",
  "Savings",
  "Inheritance",
  "Investment Returns",
  "Pension",
  "Rental Income",
  "Gift",
  "Cryptocurrency",
  "Other",
] as const;

export const ANNUAL_INCOME_OPTIONS = [
  "Under £20,000",
  "£20,000 – £50,000",
  "£50,000 – £100,000",
  "£100,000 – £250,000",
  "£250,000 – £500,000",
  "Over £500,000",
] as const;

export const INDUSTRY_OPTIONS = [
  "Financial Services",
  "Technology",
  "Healthcare",
  "Real Estate",
  "Legal",
  "Retail",
  "Manufacturing",
  "Construction",
  "Professional Services",
  "Education",
  "Media & Entertainment",
  "Other",
] as const;

export const TURNOVER_OPTIONS = [
  "Under £100,000",
  "£100,000 – £500,000",
  "£500,000 – £1,000,000",
  "£1,000,000 – £5,000,000",
  "£5,000,000 – £10,000,000",
  "Over £10,000,000",
] as const;

// ─── Profile Schema ──────────────────────────────────────────────────────────
export const profileSchema = z.object({
  customer_type: z.enum(CUSTOMER_TYPES, { error: "Customer type is required" }),
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  dob: z.string().min(1, "Date of birth is required"),
  nationality: z.string().min(1, "Nationality is required"),
  phone_number: z.string().min(7, "Valid phone number required"),
  street_address: z.string().min(5, "Street address is required"),
  city: z.string().min(1, "City is required"),
  postal_code: z.string().min(1, "Postal code is required"),
  country: z.string().min(1, "Country is required"),
});

export type ProfileFormData = z.infer<typeof profileSchema>;

// ─── KYC Schema ──────────────────────────────────────────────────────────────
export const kycSchema = z.object({
  full_name: z.string().min(2, "Full name is required"),
  dob: z.string().min(1, "Date of birth is required"),
  nationality: z.string().min(1, "Nationality is required"),
  tax_residency: z.string().min(1, "Tax residency country is required"),
  address: z.string().min(10, "Full address is required"),
  occupation: z.string().min(2, "Occupation is required"),
  source_of_funds: z.string().min(1, "Source of funds is required"),
  source_of_wealth: z
    .string()
    .min(20, "Please describe your source of wealth in detail (min 20 characters)"),
  annual_income_range: z.string().min(1, "Annual income range is required"),
  expected_activity_desc: z
    .string()
    .min(10, "Please describe your expected account activity"),
  risk_category: z.enum(RISK_CATEGORIES).default("low"),
});

export type KycFormData = z.infer<typeof kycSchema>;

// ─── Director Schema ─────────────────────────────────────────────────────────
export const directorSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  dob: z.string().optional(),
  nationality: z.string().optional(),
  appointment_date: z.string().optional(),
});

export type DirectorFormData = z.infer<typeof directorSchema>;

// ─── UBO Schema ──────────────────────────────────────────────────────────────
export const uboSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  dob: z.string().optional(),
  nationality: z.string().optional(),
  ownership_percentage: z
    .number({ error: "Must be a number" })
    .min(0.01, "Ownership must be greater than 0%")
    .max(100, "Ownership cannot exceed 100%"),
  control_type: z.string().min(1, "Control type is required"),
});

export type UboFormData = z.infer<typeof uboSchema>;

// ─── Shareholder Schema ──────────────────────────────────────────────────────
export const shareholderSchema = z.object({
  name: z.string().min(1, "Name is required"),
  share_percentage: z
    .number({ error: "Must be a number" })
    .min(0.01, "Share must be greater than 0%")
    .max(100, "Share cannot exceed 100%"),
  nationality: z.string().optional(),
  entity_type: z.enum(["individual", "corporate"]).default("individual"),
});

export type ShareholderFormData = z.infer<typeof shareholderSchema>;

// ─── Company Schema ──────────────────────────────────────────────────────────
export const companySchema = z.object({
  company_name: z.string().min(2, "Company name is required"),
  registration_number: z.string().min(1, "Registration number is required"),
  registered_address: z.string().min(10, "Registered address is required"),
  trading_address: z.string().optional(),
  country_of_incorporation: z.string().min(1, "Country of incorporation is required"),
  incorporation_date: z.string().optional(),
  sic_code: z.string().optional(),
  industry: z.string().min(1, "Industry is required"),
  tax_number: z.string().optional(),
  expected_turnover: z.string().min(1, "Expected annual turnover is required"),
  source_of_funds: z.string().min(1, "Company source of funds is required"),
  directors: z.array(directorSchema).min(1, "At least one director is required"),
  ubos: z.array(uboSchema),
  shareholders: z.array(shareholderSchema),
});

export type CompanyFormData = z.infer<typeof companySchema>;

// ─── API Response Types ──────────────────────────────────────────────────────
export type User = {
  id: string;
  email: string;
  role: "customer" | "compliance_officer" | "admin";
  is_active: boolean;
  created_at: string;
  mfa_secret?: string | null;
  mfa_enabled?: boolean;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
};

export type Customer = {
  id: string;
  customer_type: "individual" | "corporate";
  first_name?: string | null;
  last_name?: string | null;
  dob?: string | null;
  nationality?: string | null;
  phone_number?: string | null;
  street_address?: string | null;
  city?: string | null;
  postal_code?: string | null;
  country?: string | null;
  status: string;
  created_at: string;
};

export type KycProfile = {
  id: string;
  customer_id: string;
  full_name: string;
  dob: string;
  nationality: string;
  tax_residency?: string | null;
  address: string;
  occupation: string;
  source_of_funds: string;
  source_of_wealth: string;
  annual_income_range?: string | null;
  expected_activity_desc?: string | null;
  risk_category: "low" | "medium" | "high";
  created_at: string;
  updated_at: string;
};

export type DocumentRecord = {
  id: string;
  customer_id: string;
  document_type: string;
  file_name: string;
  file_path: string;
  content_type?: string | null;
  file_size?: number | null;
  verification_status: string;
  created_at: string;
};

export type OcrData = {
  full_name?: string;
  dob?: string;
  document_number?: string;
  expiry_date?: string;
  issuing_country?: string;
  [key: string]: string | undefined;
};

export type DocumentOcrResponse = {
  document_id: string;
  verification_status: string;
  ocr_data: OcrData;
  verification_metadata: Record<string, unknown>;
};

export type RiskScore = {
  id: string;
  customer_id: string;
  overall_score: number;
  risk_tier: "low" | "medium" | "high";
  breakdown: Record<string, number>;
  created_at: string;
};

export type Case = {
  id: string;
  customer_id: string;
  assigned_to?: string | null;
  priority: string;
  status: string;
  investigation_notes?: string | null;
  sar_filed: boolean;
  created_at: string;
  updated_at: string;
};

// ─── Phase 8 Types ───────────────────────────────────────────────────────────

export type Transaction = {
  id: string;
  sender_account_id: string;
  receiver_account_number: string;
  receiver_sort_code: string;
  receiver_name: string;
  receiver_country: string;
  amount: number;
  currency: string;
  transaction_type: string;
  status: string;
  reference?: string | null;
  completed_at?: string | null;
  created_at: string;
};

export type Alert = {
  id: string;
  customer_id: string;
  transaction_id?: string | null;
  alert_type: string;
  risk_score: number;
  status: string;
  alert_metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type AuditLog = {
  id: string;
  user_id?: string | null;
  action: string;
  entity_name: string;
  entity_id: string;
  old_values?: Record<string, unknown> | null;
  new_values?: Record<string, unknown> | null;
  ip_address?: string | null;
  created_at: string;
};

export type Paginated<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};

export type RescreeningResult = {
  status: string;
  customer_id: string;
  case_id?: string | null;
  score?: number | null;
  tier?: string | null;
  decision?: string | null;
  message: string;
};

export type FullCase = {
  case: Case;
  customer: {
    id: string;
    customer_type: string;
    first_name?: string;
    last_name?: string;
    nationality?: string;
    country?: string;
    status: string;
  } | null;
  kyc_profile: {
    full_name: string;
    date_of_birth?: string;
    nationality: string;
    address: string;
    source_of_funds: string;
    source_of_wealth: string;
    occupation?: string;
    risk_category: string;
    annual_income_range?: string;
    tax_residency?: string;
  } | null;
  documents: Array<{
    id: string;
    document_type: string;
    file_name: string;
    verification_status: string;
    created_at: string;
  }>;
  risk_scores: Array<{
    id: string;
    overall_score: number;
    risk_tier: string;
    breakdown: Record<string, number>;
    created_at: string;
  }>;
  alerts: Array<{
    id: string;
    alert_type: string;
    risk_score: number;
    status: string;
    alert_metadata?: Record<string, unknown>;
    created_at: string;
  }>;
  agent_logs: Array<{
    agent_name: string;
    step_name: string;
    output_state?: Record<string, unknown>;
    execution_time_ms?: number;
    created_at: string;
  }>;
};

// ─── Onboarding State ────────────────────────────────────────────────────────
export type OnboardingStep =
  | "profile"
  | "kyc"
  | "documents"
  | "company"
  | "review"
  | "submitted";

export type OnboardingDraft = {
  customerId?: string;
  customerType?: "individual" | "corporate";
  profileComplete: boolean;
  kycComplete: boolean;
  documentsComplete: boolean;
  companyComplete: boolean;
  currentStep: OnboardingStep;
  lastSaved?: string;
};

// ─── Phase 10 Types ──────────────────────────────────────────────────────────

export type Regulation = {
  id: string;
  title: string;
  authority: string;
  upload_path: string;
  uploaded_by_id?: string | null;
  created_at: string;
  description?: string | null;
  country?: string | null;
  jurisdiction?: string | null;
  regulator?: string | null;
  regulation_type?: string | null;
  version: string;
  effective_date?: string | null;
  expiry_date?: string | null;
  status: string;  // active, archived, draft, pending_review
  extracted_text?: string | null;
  document_metadata?: Record<string, unknown> | null;
};

export type PolicyRule = {
  id: string;
  regulation_id: string;
  rule_name: string;
  rule_type: string;  // threshold, block, edd, aml, kyc, internal
  conditions: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  severity: string;  // critical, high, medium, low
  description?: string | null;
  expression?: string | null;
  threshold?: number | null;
  country?: string | null;
  version: string;
};

export type RegulationVersion = {
  id: string;
  regulation_id: string;
  version: string;
  title: string;
  extracted_text: string;
  rules_snapshot: Record<string, unknown>;
  change_description?: string | null;
  author_id?: string | null;
  created_at: string;
};

// ─── Phase 11: Continuous Monitoring & Re-Screening ─────────────────────────
export type MonitoringSchedule = {
  id: string;
  customer_id: string;
  next_review_date: string;
  review_frequency_months: number;
  last_review_date?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type MonitoringJob = {
  id: string;
  customer_id: string;
  status: "queued" | "running" | "completed" | "failed";
  trigger_reason: string;
  retry_count: number;
  execution_time_ms?: number | null;
  worker_name?: string | null;
  error_message?: string | null;
  case_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type MonitoringHistory = {
  id: string;
  customer_id: string;
  screening_date: string;
  trigger_reason: string;
  old_score: number;
  new_score: number;
  old_decision: string;
  new_decision: string;
  risk_delta: number;
  new_alerts_count: number;
  resolved_alerts_count: number;
  risk_trend: "improving" | "stable" | "deteriorating";
  agents_executed: string[];
  execution_time_ms: number;
  case_id?: string | null;
  risk_score_id?: string | null;
  created_at: string;
};

export type MonitoringStatistics = {
  customers_under_monitoring: number;
  todays_screenings: number;
  queued_jobs: number;
  running_jobs: number;
  failed_jobs: number;
  upcoming_reviews: number;
  risk_changes_today: number;
  completed_reviews: number;
};

export type RiskDelta = {
  customer_id: string;
  latest_score: number;
  previous_score: number;
  delta: number;
  risk_trend: string;
  new_alerts_count: number;
};

// ─── Phase 12: Investigation Workspace ───────────────────────────────────────
export type AIAnalysisWorkspace = {
  case_summary?: string;
  suspicious_behaviour_analysis?: string;
  recommended_actions?: string[];
  questions_for_investigator?: string[];
  missing_evidence_suggestions?: string[];
  risk_explanation?: string;
};

export type Investigation = {
  id: string;
  case_id: string;
  customer_id: string;
  assigned_to?: string | null;
  assigned_supervisor_id?: string | null;
  status: "open" | "under_review" | "escalated" | "edd_required" | "closed";
  risk_level: "low" | "medium" | "high" | "critical";
  ai_summary?: AIAnalysisWorkspace | null;
  created_at: string;
  updated_at: string;
};

export type Evidence = {
  id: string;
  investigation_id: string;
  file_name: string;
  evidence_type: string;
  file_path: string;
  description?: string | null;
  uploaded_by?: string | null;
  timestamp: string;
  file_hash: string;
};

export type CaseNote = {
  id: string;
  investigation_id: string;
  author_id?: string | null;
  note_text: string;
  created_at: string;
  updated_at: string;
};

export type SAR = {
  id: string;
  investigation_id: string;
  sar_number: string;
  narrative: string;
  reason: string;
  risk_indicators: string[];
  recommendation: string;
  status: "draft" | "submitted" | "approved" | "rejected" | "archived";
  created_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type TimelineEvent = {
  id: string;
  investigation_id: string;
  event_type: string;
  title: string;
  description: string;
  actor_id?: string | null;
  timestamp: string;
};

export type Assignment = {
  id: string;
  investigation_id: string;
  assigned_by?: string | null;
  assigned_to?: string | null;
  role: "investigator" | "supervisor";
  assigned_at: string;
};

export type InvestigatorWorkload = {
  user_id: string;
  email: string;
  active_cases: number;
};

export type InvestigationDashboardMetrics = {
  open_investigations: number;
  pending_sar: number;
  sar_submitted: number;
  evidence_uploaded: number;
  average_investigation_time_hours: number;
  investigator_workload: InvestigatorWorkload[];
  recently_assigned_cases: {
    investigation_id: string;
    customer_name: string;
    status: string;
    risk_level: string;
    created_at: string;
  }[];
};

export type InvestigationWorkspacePayload = {
  investigation: Investigation;
  customer?: Customer | null;
  kyc_profile?: KycProfile | null;
  documents: DocumentRecord[];
  alerts: Alert[];
  transactions: Transaction[];
  risk_scores: RiskScore[];
  monitoring_history: MonitoringHistory[];
  notes: CaseNote[];
  evidence: Evidence[];
  sars: SAR[];
  timeline: TimelineEvent[];
  assignments: Assignment[];
};

// ─── Phase 13: Reporting & BI System Types ────────────────────────────────────
export type ReportTemplate = {
  id: string;
  name: string;
  description?: string | null;
  config: Record<string, any>;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type Report = {
  id: string;
  name: string;
  template_id?: string | null;
  generated_by?: string | null;
  status: "pending" | "completed" | "failed";
  format: "pdf" | "excel" | "csv" | "json";
  file_path?: string | null;
  filters: Record<string, any>;
  created_at: string;
};

export type ScheduledReport = {
  id: string;
  name: string;
  template_id: string;
  cron_expression: string;
  next_run: string;
  status: "active" | "paused" | "deleted";
  created_by?: string | null;
  created_at: string;
};

export type ReportExecution = {
  id: string;
  schedule_id: string;
  report_id?: string | null;
  status: "success" | "failed";
  error_message?: string | null;
  executed_at: string;
};

export type DashboardWidget = {
  id: string;
  layout_id: string;
  widget_type: string;
  title: string;
  config: Record<string, any>;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
};

export type DashboardLayout = {
  id: string;
  name: string;
  user_id?: string | null;
  is_default: boolean;
  config: Record<string, any>;
  created_at: string;
  widgets: DashboardWidget[];
};

export type PeriodicKPIs = {
  period: string;
  metrics: {
    new_customers: number;
    total_customers: number;
    kyc_completion_rate: number;
    average_risk_score: number;
    cases_opened: number;
    cases_closed: number;
    alerts_created: number;
    sars_filed: number;
    transactions_screened: number;
    monitoring_jobs: number;
    agent_executions: number;
    agent_success_rate: number;
  };
  distributions: {
    risk_category: Record<string, number>;
    top_alerts: { type: string; count: number }[];
    country_distribution: { country: string; count: number }[];
  };
};


// ─── PHASE 14 — External Integrations & Notifications ─────────────────────

export interface IntegrationSetting {
  id: string;
  provider_name: string;
  provider_type: string;
  base_url?: string;
  enabled: boolean;
  timeout: number;
  configuration: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface IntegrationSettingCreate {
  provider_name: string;
  provider_type: string;
  base_url?: string;
  api_key?: string;
  api_secret?: string;
  enabled: boolean;
  timeout: number;
  configuration: Record<string, unknown>;
}

export interface SyncHistory {
  id: string;
  provider: string;
  sync_type: string;
  started_at: string;
  completed_at?: string;
  records_processed: number;
  records_added: number;
  records_updated: number;
  records_failed: number;
  status: string;
  error_message?: string;
}

export interface NotificationTemplate {
  id: string;
  name: string;
  event_type: string;
  channel: string;
  subject?: string;
  body: string;
  variables: string[];
  active: boolean;
  created_at: string;
}

export interface Notification {
  id: string;
  user_id?: string;
  template_id?: string;
  channel: string;
  title: string;
  message: string;
  priority: string;
  status: string;
  sent_at?: string;
  retry_count: number;
  created_at: string;
}

export interface WebhookEndpoint {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  events: string[];
  retries: number;
  created_at: string;
}

export interface WebhookLog {
  id: string;
  endpoint_id: string;
  event: string;
  signature?: string;
  response_code?: number;
  response_body?: string;
  status: string;
  retry_count: number;
  created_at: string;
}

export interface ProviderHealth {
  provider: string;
  status: string;
  latency_ms: number;
  mock_mode: boolean;
  version: string;
  last_sync?: string;
  last_sync_status: string;
}

export interface SendNotificationRequest {
  event_type: string;
  channels: string[];
  variables: Record<string, string>;
  to_email?: string;
  priority?: string;
  user_id?: string;
}

// ─── Phase 15: Enterprise Security & Observability ──────────────────────────

export interface MFAEnrollData {
  secret: string;
  qr_code_base64: string;
  backup_codes: string[];
  otpauth_uri: string;
}

export interface MFASetupResponse {
  success: boolean;
  message: string;
}

export interface LoginHistoryEntry {
  id: string;
  user_id?: string;
  email?: string;
  ip_address?: string;
  user_agent?: string;
  success: boolean;
  failure_reason?: string;
  country?: string;
  created_at: string;
}

export interface BackupRecord {
  id: string;
  backup_type: string;
  file_name: string;
  file_size_bytes?: number;
  sha256_checksum?: string;
  status: string;
  triggered_by: string;
  error_message?: string;
  expires_at?: string;
  created_at: string;
  completed_at?: string;
}

export interface SystemHealthDetails {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

export interface DbHealthDetails {
  status: string;
  latency_ms: number;
  users_count: number;
  cases_count: number;
  alerts_count: number;
}

export interface RedisHealthDetails {
  status: string;
  latency_ms: number;
}

export interface CeleryHealthDetails {
  status: string;
  queue_length: number;
  active_workers: number;
}

export interface ApiStatsDetails {
  request_count_1h: number;
  average_latency_ms: number;
  error_rate_percent: number;
  slow_requests_count: number;
}

export interface CacheStatsDetails {
  backend: string;
  hits: number;
  misses: number;
  sets: number;
  deletes: number;
  hit_rate: number;
}

export interface FullObservabilityReport {
  timestamp: string;
  active_users_15m: number;
  system: SystemHealthDetails;
  database: DbHealthDetails;
  redis: RedisHealthDetails;
  celery: CeleryHealthDetails;
  api_stats: ApiStatsDetails;
  cache: CacheStatsDetails;
}

// ─── Phase 16: DevOps & Infrastructure ────────────────────────────────────────

export interface DevOpsPodInfo {
  name: string;
  status: string;
  restarts: number;
  ip: string;
  age: string;
  cpu: string;
  memory: string;
}

export interface DevOpsDbStatus {
  primary_status: string;
  primary_latency_ms: number;
  replica_status: string;
  replica_latency_ms: number;
  replica_lag_ms: number;
  pool_metrics: {
    primary: { pool_size: number; checked_out: number; overflow: number };
    replica: { pool_size: number; checked_out: number; overflow: number };
  };
}

export interface DevOpsRedisStatus {
  status: string;
  latency_ms: number;
  sentinel_active: boolean;
  cluster_active: boolean;
  sentinel_service_name: string;
  connected_clients: number;
  cache_hit_rate: number;
  keys_count: number;
}

export interface DevOpsCeleryStatus {
  queue_length: number;
  active_workers_count: number;
  active_workers: string[];
  active_tasks_count: number;
}

export interface DevOpsStatusReport {
  deployment_version: string;
  docker_image_version: string;
  git_commit: string;
  kubernetes_namespace: string;
  uptime_seconds: number;
  uptime: string;
  restart_count: number;
  system: SystemHealthDetails;
  database: DevOpsDbStatus;
  redis: DevOpsRedisStatus;
  celery: DevOpsCeleryStatus;
  pods_count: number;
  pods: DevOpsPodInfo[];
  active_users: number;
  average_screening_time_sec: number;
}

// ─── Phase 17: AI Governance & Explainability ────────────────────────────────

export interface AIModel {
  id: string;
  name: string;
  provider: string;
  is_active: boolean;
  versions: ModelVersion[];
}

export interface ModelVersion {
  id: string;
  version: string;
  is_active: boolean;
  metadata: Record<string, any>;
}

export interface PromptTemplate {
  id: string;
  name: string;
  description?: string;
  versions: PromptVersion[];
}

export interface PromptVersion {
  id: string;
  version: string;
  content: string;
  is_active: boolean;
  approved_status: string; // 'draft', 'pending', 'approved', 'rejected', 'published'
  created_at: string;
}

export interface AIExecution {
  id: string;
  customer_id?: string;
  prompt_content?: string;
  response_content?: string;
  cost: number;
  latency_ms: number;
  tokens_used: number;
  input_tokens: number;
  output_tokens: number;
  created_at: string;
}

export interface AIExplanation {
  id: string;
  execution_id: string;
  decision_summary: string;
  reasoning_tree: Record<string, any>;
  confidence: number;
  supporting_evidence?: string;
  matched_rules?: string;
  matched_entities?: string;
  missing_evidence?: string;
  recommended_actions?: string;
  created_at: string;
}

export interface AIFeedback {
  id: string;
  execution_id: string;
  rating: number;
  is_correct: boolean;
  is_helpful: boolean;
  comments?: string;
  decision_override?: string;
  escalation_reason?: string;
}

export interface ModelEvaluation {
  id: string;
  model_version_id: string;
  evaluator: string;
  metrics: Record<string, any>;
  created_at: string;
}

export interface AIPolicy {
  id: string;
  name: string;
  description?: string;
  rules: Record<string, any>;
  is_active: boolean;
}

export interface AIStatistics {
  active_models_count: number;
  total_executions: number;
  average_confidence: number;
  average_cost: number;
  total_cost_usd: number;
  average_latency_ms: number;
  human_feedback_score: number;
  success_rate: number;
}

export interface AIUsage {
  date: string;
  model_name: string;
  total_calls: number;
  total_tokens: number;
  total_cost: number;
  average_latency_ms: number;
}



