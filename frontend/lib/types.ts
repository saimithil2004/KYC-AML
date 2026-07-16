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
  priority: string;
  status: string;
  investigation_notes?: string | null;
  sar_filed: boolean;
  created_at: string;
  updated_at: string;
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
