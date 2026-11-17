// Single source of truth for the active-session localStorage key.
// Used by /login (writes) and the dashboard (reads + clears).

export const SESSION_KEY = "wallet:active-user-id";
export const ADMIN_SESSION_KEY = "wallet:admin-token";

export function readActiveUserId(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(SESSION_KEY);
    if (!v) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

export function writeActiveUserId(id: number): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(SESSION_KEY, String(id));
  } catch {
    // ignore
  }
}

export function clearActiveUserId(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}

export function readAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(ADMIN_SESSION_KEY);
  } catch {
    return null;
  }
}

export function writeAdminToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(ADMIN_SESSION_KEY, token);
  } catch {
    // ignore
  }
}

export function clearAdminToken(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(ADMIN_SESSION_KEY);
  } catch {
    // ignore
  }
}