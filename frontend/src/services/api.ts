import type {
  TokenResponse,
  Memo,
  ECLResult,
  AuditLogEntry,
  ReportSummary,
  GenerateMemoRequest,
  GenerateMemoResponse,
  MemoListItem,
  NotificationItem,
  EscalationItem,
  UserAccount,
  ClientProfile,
} from "../types/api";

const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/v1`
  : "/api/v1";

function headers(): Record<string, string> {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// --- Auth ---
export async function login(username: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/token", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

// --- Memos ---
export async function generateMemo(req: GenerateMemoRequest): Promise<GenerateMemoResponse> {
  return request<GenerateMemoResponse>("/generate-memo", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getMemos(): Promise<{ memos: MemoListItem[] }> {
  return request<{ memos: MemoListItem[] }>("/memos");
}

export async function getMemo(id: string): Promise<Memo> {
  return request<Memo>(`/memo/${id}`);
}

export async function approveSection(
  memoId: string,
  sectionKey: string,
  comment: string,
): Promise<unknown> {
  return request(`/memo/${memoId}/approve`, {
    method: "POST",
    body: JSON.stringify({ section_key: sectionKey, comment }),
  });
}

export async function rejectSection(
  memoId: string,
  sectionKey: string,
  comment: string,
): Promise<unknown> {
  return request(`/memo/${memoId}/reject`, {
    method: "POST",
    body: JSON.stringify({ section_key: sectionKey, comment }),
  });
}

export async function finalizeMemo(memoId: string): Promise<unknown> {
  return request(`/memo/${memoId}/finalize`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getMemoWorkflow(id: string): Promise<unknown> {
  return request(`/memo/${id}/workflow`);
}

export async function getMemoAuditLog(id: string): Promise<{ entries: AuditLogEntry[] }> {
  return request<{ entries: AuditLogEntry[] }>(`/memo/${id}/audit-log`);
}

export async function notifyMemo(id: string): Promise<unknown> {
  return request(`/memo/${id}/notify`, { method: "POST" });
}

// --- ECL ---
export async function computeECL(params?: {
  portfolio_size?: number;
  total_gross_financing?: number;
  npl_ratio?: number;
}): Promise<ECLResult> {
  return request<ECLResult>("/risk/ecl", {
    method: "POST",
    body: JSON.stringify({
      portfolio_size: params?.portfolio_size ?? 200,
      total_gross_financing: params?.total_gross_financing ?? 4_150_000_000,
      npl_ratio: params?.npl_ratio ?? 0.0145,
    }),
  });
}

// --- Audit ---
export async function getAuditLog(): Promise<{ entries: AuditLogEntry[] }> {
  return request<{ entries: AuditLogEntry[] }>("/audit-log");
}

// --- Reports ---
export async function getReport(reportType: string): Promise<ReportSummary> {
  return request<ReportSummary>(`/reports/${reportType}`);
}

// --- Notifications ---
export async function getNotifications(): Promise<{
  notifications: NotificationItem[];
  unread_count: number;
}> {
  return request<{ notifications: NotificationItem[]; unread_count: number }>(
    "/notifications",
  );
}

export async function markNotificationRead(id: string): Promise<unknown> {
  return request(`/notifications/${id}/read`, { method: "POST" });
}

// --- Escalations ---
export async function getEscalations(): Promise<{ escalations: EscalationItem[] }> {
  return request<{ escalations: EscalationItem[] }>("/escalations");
}

export async function checkEscalations(): Promise<{ triggered: unknown[] }> {
  return request<{ triggered: unknown[] }>("/escalations/check", { method: "POST" });
}

// --- Users ---
export async function getUsers(): Promise<{ users: UserAccount[] }> {
  return request<{ users: UserAccount[] }>("/users");
}

export async function createUser(user: {
  username: string;
  password: string;
  full_name: string;
  email?: string;
  role: string;
}): Promise<UserAccount> {
  return request<UserAccount>("/users", {
    method: "POST",
    body: JSON.stringify(user),
  });
}

// --- Clients ---
export async function getClients(): Promise<{ clients: ClientProfile[] }> {
  return request<{ clients: ClientProfile[] }>("/clients");
}
