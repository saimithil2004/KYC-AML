export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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
  address: string;
  occupation: string;
  source_of_funds: string;
  source_of_wealth: string;
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

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
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

export async function ensureCustomer(token: string): Promise<Customer> {
  try {
    return await apiRequest<Customer>("/customers/me", {}, token);
  } catch {
    return apiRequest<Customer>(
      "/customers/",
      {
        method: "POST",
        body: JSON.stringify({ customer_type: "individual" }),
      },
      token,
    );
  }
}
