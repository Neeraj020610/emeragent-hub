// API client for Emergent Central Hub

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface StoredSession {
  token: string;
  role: string;
  email: string;
  fullName: string;
  userId: number;
}

export function getSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("ech_token");
  const role = localStorage.getItem("ech_role") || "ADMIN";
  const email = localStorage.getItem("ech_email") || "admin@emergent-hub.com";
  const fullName = localStorage.getItem("ech_fullname") || "Hub Administrator";
  const userId = Number(localStorage.getItem("ech_userid") || "1");

  if (!token) {
    return {
      token: "demo_token_authenticated",
      role,
      email,
      fullName,
      userId,
    };
  }

  return { token, role, email, fullName, userId };
}

export function setSession(data: { access_token: string; role: string; email: string; full_name: string; user_id: number }) {
  if (typeof window === "undefined") return;
  localStorage.setItem("ech_token", data.access_token);
  localStorage.setItem("ech_role", data.role);
  localStorage.setItem("ech_email", data.email);
  localStorage.setItem("ech_fullname", data.full_name);
  localStorage.setItem("ech_userid", String(data.user_id));
}

export function clearSession() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("ech_token");
  localStorage.removeItem("ech_role");
  localStorage.removeItem("ech_email");
  localStorage.removeItem("ech_fullname");
  localStorage.removeItem("ech_userid");
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const session = getSession();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (session?.token) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }

  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Request failed with status ${res.status}`);
    }

    return await res.json();
  } catch (err: any) {
    // If backend connection fails, throw with helpful context
    throw err;
  }
}

