// API client. All requests proxy through Next.js rewrites to the FastAPI
// backend at 127.0.0.1:8000 (configured in next.config.js). The frontend
// never talks to a different origin.

export type User = {
  id: number;
  handle: string;
  display_name: string;
  phone: string;
  email?: string;
  user_type?: string;
  account_tier?: string;
  effective_tier?: string;
  kyc_status?: string;
  business_name?: string | null;
  masked_phone?: string;
  created_at?: string;
  daily_limit?: string | number | null;
  single_txn_limit?: string | number | null;
  effective_single_limit?: number;
  effective_daily_limit?: number;
  requested_upgrade_tier?: string | null;
  requested_upgrade_at?: string | null;
};

export type UserProfileDetails = {
  user: User;
  current_balance_bdt: string;
  daily_spent_today_bdt: string;
  daily_limit_bdt: string;
  daily_remaining_bdt: string;
  daily_usage_pct: number;
  frequent_recipients: {
    user_id: number;
    handle: string;
    display_name: string;
    tier: string;
    count: number;
  }[];
  baseline_median_30d: number;
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

// ---- New Intelligence Layer Types ------------------------------------------
export type FinancialRecommendation = {
  id: string;
  title: string;
  category: string;
  priority: "high" | "medium" | "low";
  description: string;
  action_label: string;
};

export type CategorySpendBreakdown = {
  category: string;
  amount_bdt: string;
  percentage: number;
  amount_raw: number;
};

export type FinancialIntelligence = {
  user_id: number;
  health_score: number;
  health_rating: string;
  health_color: string;
  current_balance_bdt: string;
  total_spent_30d_bdt: string;
  total_spent_7d_bdt: string;
  count_30d: number;
  count_7d: number;
  weekly_velocity_pct: number;
  category_breakdown: CategorySpendBreakdown[];
  recommendations: FinancialRecommendation[];
  text: string;
};

export type FinancialLiteracyTopic = {
  slug: string;
  title: string;
  summary: string;
  bangla_summary: string;
  details?: string;
  key_takeaways?: string[];
  text?: string;
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

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retries = 3,
  delay = 2500
): Promise<Response> {
  try {
    const res = await fetch(url, options);
    if ((res.status === 502 || res.status === 503 || res.status === 504) && retries > 0) {
      console.warn(`[API] Backend returned ${res.status} (container waking up?), retrying in ${delay}ms...`);
      await new Promise((r) => setTimeout(r, delay));
      return fetchWithRetry(url, options, retries - 1, delay * 1.3);
    }
    return res;
  } catch (err) {
    if (retries > 0) {
      console.warn(`[API] Fetch error for ${url}, retrying in ${delay}ms...`, err);
      await new Promise((r) => setTimeout(r, delay));
      return fetchWithRetry(url, options, retries - 1, delay * 1.3);
    }
    throw err;
  }
}

async function httpJson<T>(
  method: string,
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  const r = await fetchWithRetry(`${BASE}${path}`, {
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
  const r = await fetchWithRetry(path, {
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
  getUserProfile: (id: number) => httpJson<UserProfileDetails>("GET", `/users/${id}/profile`),
  requestUserUpgrade: (
    userId: number,
    body: { requested_tier: string; business_name?: string; reason?: string }
  ) =>
    httpJson<{
      success: boolean;
      message: string;
      requested_tier: string;
      kyc_status: string;
      effective_tier: string;
    }>("POST", `/users/${userId}/upgrade-request`, body),
  getTierConfig: () => httpJson<Record<string, unknown>>("GET", "/tier-config"),
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

  // ---- New Intelligence Layer: Financial Intelligence & Literacy -----------
  getFinancialIntelligence: (userId: number) =>
    httpJson<FinancialIntelligence>("GET", `/users/${userId}/financial-intelligence`),
  getFinancialLiteracy: (userId: number, topic?: string) =>
    httpJson<{
      topics?: FinancialLiteracyTopic[];
      topic?: string;
      title?: string;
      summary?: string;
      details?: string;
      bangla_summary?: string;
      key_takeaways?: string[];
      text: string;
    }>(
      "GET",
      `/users/${userId}/financial-literacy${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`
    ),
  getRecommendationAdvice: (
    userId: number,
    body: { title: string; description?: string; category?: string }
  ) =>
    httpJson<{
      title: string;
      advice: string;
      action_steps: string[];
      live_facts: Record<string, unknown>;
    }>("POST", `/users/${userId}/financial-intelligence/advice`, body),

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
  getAdminUser: (userId: number) =>
    adminHttpJson<any>("GET", `/admin/api/users/${userId}`),
  adminVerifyKYC: (
    userId: number,
    body: { kyc_status: "verified" | "unverified"; notes?: string; activate_requested_tier?: boolean }
  ) =>
    adminHttpJson<{
      success: boolean;
      user_id: number;
      kyc_status: string;
      account_tier: string;
      effective_tier: string;
    }>("PATCH", `/admin/api/users/${userId}/kyc`, body),
  adminChangeTier: (
    userId: number,
    body: {
      account_tier: string;
      reason_code: string;
      notes?: string;
      user_type?: string;
      single_txn_limit?: number;
      daily_limit?: number;
    }
  ) =>
    adminHttpJson<{
      success: boolean;
      user_id: number;
      account_tier: string;
      kyc_status: string;
      effective_tier: string;
      reason_code: string;
    }>("PATCH", `/admin/api/users/${userId}/tier`, body),
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
  updateFraudAlert: (
    alertId: number,
    body: { status: string; reason_code?: string; notes?: string; assign_to_me?: boolean }
  ) =>
    adminHttpJson<{
      success: boolean;
      alert_id: number;
      status: string;
      reason_code?: string;
      is_confirmed_fraud?: boolean;
    }>("PATCH", `/admin/api/fraud/alerts/${alertId}`, body),
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
  queryAdminAI: (
    query: string,
    history?: { sender: "admin" | "ai"; text: string }[]
  ) =>
    adminHttpJson<{
      intent: string;
      response: string;
      data: any;
      timestamp: string;
    }>("POST", "/admin/api/ai/query", { query, history }),
};

/**
 * Mask sensitive customer/sender phone numbers in the UI (e.g. 01926240062 -> 0192****062).
 */
export function maskPhone(phone?: string | null): string {
  if (!phone) return "";
  const cleaned = phone.trim();
  if (cleaned.length < 8) return cleaned;
  return `${cleaned.slice(0, 4)}****${cleaned.slice(-3)}`;
}
