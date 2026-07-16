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
} from "./types";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
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
): Promise<{ document_id: string; verification_status: string; ocr_data: Record<string, string>; verification_metadata: Record<string, unknown> }> {
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
