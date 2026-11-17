// API client. All requests proxy through Next.js rewrites to the FastAPI
// backend at 127.0.0.1:8000 (configured in next.config.js). The frontend
// never talks to a different origin.

export type User = {
  id: number;
  handle: string;
  display_name: string;
  phone: string;
  email?: string;
};

export type Txn = {
  id: number;
  kind: string;
  status: string;
  amount_bdt: string;
  direction: "in" | "out";
  counterparty: string | null;
  counterparty_phone: string | null;
  note: string | null;
  created_at: string;
  completed_at: string | null;
};

export type PendingRequest = {
  id: number;
  asker_handle: string;
  asker_phone: string;
  amount_bdt: string;
  note: string | null;
  created_at: string;
};

export type SavingsGoal = {
  id: number;
  festival: string;
  target_amount_bdt: string;
  saved_amount_bdt: string;
  target_date: string | null;
};

// ---- Face ID ---------------------------------------------------------------
// 128-dim float vector produced by face-api.js. Stored on the server as an
// opaque JSON blob — the API never echoes it back, so the frontend only
// ever writes it on enrollment.
export type FaceEmbedding = number[];

export type FaceStatus = {
  user_id: number;
  enrolled: boolean;
  enrolled_at: string | null;
};

export type ReviewCard = {
  kind: "send" | "request" | "split" | "pay_bill";
  amount_bdt: string;
  recipient_label?: string | null;
  recipient_phone?: string | null;
  recipients?: string[] | null;
  note?: string | null;
  resulting_balance_bdt: string;
  initiator_handle: string;
  initiator_phone: string;
  risk_level?: "low" | "medium" | "high" | null;
  risk_score?: number | null;
  security_analysis?: string[] | null;
  requires_biometric?: boolean | null;
};

export type AgentActResponse = {
  text: string;
  card?: ReviewCard | null;
  pending_id?: number | null;
  action: string;
  idempotent_replay?: boolean;
  data?: Record<string, unknown> | null;
};

export type AgentConfirmResponse = {
  text: string;
  success: boolean;
  new_balance_bdt?: string | null;
  data?: Record<string, unknown> | null;
};

export type HistoryResponse = {
  user_id: number;
  handle: string;
  balance_bdt: string;
  txns: Txn[];
  timeline: { date: string; balance: number }[];
};

import { readAdminToken } from "./session";

const BASE = "/api";

/**
 * Synthesize speech through the configured backend TTS engine.
 *
 * Returns the raw WAV bytes as a Blob. Throws on non-2xx — the frontend
 * must NOT fall back to a browser-default voice if the backend engine
 * fails, because that's exactly the bug we're fixing.
 */
export async function speak(text: string): Promise<Blob> {
  const r = await fetch(`${BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) detail += `: ${JSON.stringify(j.detail)}`;
    } catch {
      /* ignore */
    }
    throw new Error(`speak ${detail}`);
  }
  return r.blob();
}

async function httpJson<T>(
  method: string,
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    ...init,
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) detail += `: ${JSON.stringify(j.detail)}`;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

async function adminHttpJson<T>(
  method: string,
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  const token = readAdminToken();
  const headers: Record<string, string> = {
    ...(body ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers as Record<string, string>) || {}),
  };
  const r = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    ...init,
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) detail += `: ${JSON.stringify(j.detail)}`;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

export const api = {
  login: (email: string, password?: string) =>
    httpJson<User>("POST", "/auth/login", { email, password: password || "" }),
  listUsers: () => httpJson<User[]>("GET", "/users"),
  getUser: (id: number) => httpJson<User>("GET", `/users/${id}`),
  getUserByHandle: (handle: string) =>
    httpJson<User>("GET", `/users/handle/${handle}`),
  getBalance: (id: number) =>
    httpJson<{ user_id: number; handle: string; balance_bdt: string; as_of: string }>(
      "GET",
      `/users/${id}/balance`
    ),
  getHistory: (id: number) => httpJson<HistoryResponse>("GET", `/users/${id}/history`),
  getRequests: (id: number) => httpJson<PendingRequest[]>("GET", `/users/${id}/requests`),
  getSavingsGoals: (id: number) => httpJson<SavingsGoal[]>("GET", `/users/${id}/savings-goals`),
  createSavingsGoal: (id: number, body: { festival: string; target_amount_bdt: string }) =>
    httpJson<SavingsGoal>("POST", `/users/${id}/savings-goals`, body),
  contributeSavings: (id: number, goalId: number, body: { amount_bdt: string; idempotency_key: string }) =>
    httpJson<SavingsGoal>("POST", `/users/${id}/savings-goals/${goalId}/contribute`, body),
  listBillers: () =>
    httpJson<{ id: number; name: string; category: string; account_number: string }[]>(
      "GET",
      "/billers"
    ),
  agentAct: (body: { user_id: number; text: string; idempotency_key: string }) =>
    httpJson<AgentActResponse>("POST", "/agent/act", body),
  agentActSend: (body: {
    user_id: number;
    recipient_handle: string;
    amount_bdt: string;
    note?: string;
    idempotency_key: string;
  }) => httpJson<AgentActResponse>("POST", "/agent/act-send", body),
  agentActRequest: (body: {
    user_id: number;
    payer_handle: string;
    amount_bdt: string;
    note?: string;
    idempotency_key: string;
  }) => httpJson<AgentActResponse>("POST", "/agent/act-request", body),
  agentActSplit: (body: {
    user_id: number;
    recipient_handles: string[];
    amount_bdt: string;
    note?: string;
    idempotency_key: string;
  }) => httpJson<AgentActResponse>("POST", "/agent/act-split", body),
  agentConfirm: (body: {
    user_id: number;
    pending_id: number;
    idempotency_key: string;
    decision: "confirm" | "decline";
  }) => httpJson<AgentConfirmResponse>("POST", "/agent/confirm", body),
  agentChat: (body: { user_id: number; text: string }) =>
    httpJson<{ text: string; action: string }>("POST", "/agent/chat", body),
  payRequest: (requestId: number, idempotencyKey: string, userId: number) =>
    httpJson<{ success: boolean; new_balance_bdt: string }>(
      "POST",
      `/requests/${requestId}/pay?idempotency_key=${encodeURIComponent(idempotencyKey)}&user_id=${userId}`
    ),
  declineRequest: (requestId: number) =>
    httpJson<{ success: boolean }>("POST", `/requests/${requestId}/decline`),
  transcribe: async (blob: Blob): Promise<string> => {
    const fd = new FormData();
    fd.append("audio", blob, "audio.webm");
    const r = await fetch(`${BASE}/voice/transcribe`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(`transcribe ${r.status}`);
    const j = await r.json();
    return j.text as string;
  },
  getHealth: () => httpJson<{
    ok: boolean;
    ollama_reachable: boolean;
    ollama_url: string;
    openrouter_reachable: boolean;
    openrouter_configured: boolean;
    regex_fallback: boolean;
  }>("GET", "/health"),
  getSettings: () => httpJson<Record<string, unknown>>("GET", "/settings"),
  patchSettings: (patch: Record<string, unknown>) =>
    httpJson<Record<string, unknown>>("PATCH", "/settings", patch),

  // ---- Face ID -----------------------------------------------------------
  getFaceStatus: (userId: number) =>
    httpJson<FaceStatus>("GET", `/users/${userId}/face/status`),
  enrollFace: (userId: number, embedding: FaceEmbedding) =>
    httpJson<FaceStatus>("POST", `/users/${userId}/face`, { embedding }),
  deleteFace: (userId: number) =>
    httpJson<{ user_id: number; enrolled: boolean }>("DELETE", `/users/${userId}/face`),

  // ---- User Security Preferences (Requirement 7) -------------------------
  getUserSecurityPreference: (userId: number) =>
    httpJson<{ user_id: number; show_security_analysis: boolean }>(
      "GET",
      `/users/${userId}/security-preference`
    ),
  setUserSecurityPreference: (userId: number, show: boolean) =>
    httpJson<{ user_id: number; show_security_analysis: boolean }>(
      "POST",
      `/users/${userId}/security-preference`,
      { show_security_analysis: show }
    ),

  // ---- Dedicated Admin Intelligence Platform ------------------------------
  adminLogin: (body: { phone: string; password: string }) =>
    adminHttpJson<{
      token: string;
      expires_at: string;
      admin: { id: number; phone: string; display_name: string; role: string };
    }>("POST", "/admin/api/auth/login", body),
  adminMe: () =>
    adminHttpJson<{
      id: number;
      phone: string;
      display_name: string;
      role: string;
      last_login_at: string | null;
    }>("GET", "/admin/api/auth/me"),
  adminLogout: () =>
    adminHttpJson<{ success: boolean; message: string }>("POST", "/admin/api/auth/logout"),
  getAdminOverview: () =>
    adminHttpJson<{
      kpis: {
        total_users: number;
        active_users: number;
        total_transactions: number;
        completed_transactions: number;
        failed_cancelled_transactions: number;
        total_volume_bdt: number;
        suspicious_transactions: number;
        high_risk_transactions: number;
        pending_investigations: number;
      };
      charts: {
        activity_timeline: { date: string; volume_bdt: number; transactions: number; alerts: number }[];
        risk_distribution: { name: string; count: number; color: string }[];
      };
    }>("GET", "/admin/api/overview"),
  getAdminFraudAssessments: (params?: {
    page?: number;
    page_size?: number;
    risk_level?: string;
    status?: string;
    search?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set("page", String(params.page));
    if (params?.page_size) sp.set("page_size", String(params.page_size));
    if (params?.risk_level) sp.set("risk_level", params.risk_level);
    if (params?.status) sp.set("status", params.status);
    if (params?.search) sp.set("search", params.search);
    return adminHttpJson<{
      items: any[];
      total: number;
      page: number;
      page_size: number;
      pages: number;
    }>("GET", `/admin/api/fraud/assessments?${sp.toString()}`);
  },
  getAdminFraudAssessment: (id: number) =>
    adminHttpJson<any>("GET", `/admin/api/fraud/assessments/${id}`),
  reviewFraudAssessment: (id: number, body: { decision: string; notes?: string }) =>
    adminHttpJson<{ success: boolean; assessment_id: number; new_status: string }>(
      "POST",
      `/admin/api/fraud/assessments/${id}/review`,
      body
    ),
  getAdminTransactions: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    risk_level?: string;
    search?: string;
    min_amount?: number;
    max_amount?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set("page", String(params.page));
    if (params?.page_size) sp.set("page_size", String(params.page_size));
    if (params?.status) sp.set("status", params.status);
    if (params?.risk_level) sp.set("risk_level", params.risk_level);
    if (params?.search) sp.set("search", params.search);
    if (params?.min_amount !== undefined) sp.set("min_amount", String(params.min_amount));
    if (params?.max_amount !== undefined) sp.set("max_amount", String(params.max_amount));
    return adminHttpJson<{
      items: any[];
      total: number;
      page: number;
      page_size: number;
      pages: number;
    }>("GET", `/admin/api/transactions?${sp.toString()}`);
  },
  getAdminTransaction: (id: number) =>
    adminHttpJson<any>("GET", `/admin/api/transactions/${id}`),
  getAdminUsers: (params?: { search?: string; status_filter?: string }) => {
    const sp = new URLSearchParams();
    if (params?.search) sp.set("search", params.search);
    if (params?.status_filter) sp.set("status_filter", params.status_filter);
    return adminHttpJson<{ users: any[]; count: number }>(
      "GET",
      `/admin/api/users?${sp.toString()}`
    );
  },
  toggleUserFlag: (userId: number, reason?: string) =>
    adminHttpJson<{ success: boolean; user_id: number; is_flagged: boolean }>(
      "POST",
      `/admin/api/users/${userId}/flag`,
      { reason }
    ),
  toggleUserFreeze: (userId: number, reason?: string) =>
    adminHttpJson<{ success: boolean; user_id: number; is_frozen: boolean }>(
      "POST",
      `/admin/api/users/${userId}/freeze`,
      { reason }
    ),
  getFraudAlerts: (params?: { status?: string; severity?: string; page?: number; page_size?: number }) => {
    const sp = new URLSearchParams();
    if (params?.status) sp.set("status", params.status);
    if (params?.severity) sp.set("severity", params.severity);
    if (params?.page) sp.set("page", String(params.page));
    if (params?.page_size) sp.set("page_size", String(params.page_size));
    return adminHttpJson<{ items: any[]; total: number; page: number; page_size: number; pages: number }>(
      "GET",
      `/admin/api/fraud/alerts?${sp.toString()}`
    );
  },
  updateFraudAlert: (alertId: number, body: { status: string; notes?: string; assign_to_me?: boolean }) =>
    adminHttpJson<{ success: boolean; alert_id: number; status: string }>(
      "PATCH",
      `/admin/api/fraud/alerts/${alertId}`,
      body
    ),
  getAdminAuditLogs: (params?: { page?: number; page_size?: number }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set("page", String(params.page));
    if (params?.page_size) sp.set("page_size", String(params.page_size));
    return adminHttpJson<{ items: any[]; total: number; page: number; page_size: number }>(
      "GET",
      `/admin/api/audit-logs?${sp.toString()}`
    );
  },
  getSystemStatus: () =>
    adminHttpJson<{
      service: string;
      timestamp: string;
      database: any;
      fraud_detection_engine: any;
      ai_cascade_infrastructure: any;
    }>("GET", "/admin/api/system/status"),
  queryAdminAI: (query: string) =>
    adminHttpJson<{
      intent: string;
      response: string;
      data: any;
      timestamp: string;
    }>("POST", "/admin/api/ai/query", { query }),
};