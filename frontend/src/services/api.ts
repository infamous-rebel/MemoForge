import type {
  TokenResponse,
  Memo,
  ECLResult,
  AuditLogEntry,
  ReportSummary,
  GenerateMemoRequest,
} from "../types/api";

const BASE = "/api/v1";

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
export async function generateMemo(req: GenerateMemoRequest): Promise<Memo> {
  return request<Memo>("/generate-memo", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getMemo(id: string): Promise<Memo> {
  return request<Memo>(`/memo/${id}`);
}

export async function approveSection(
  memoId: string,
  sectionKey: string,
  comments: string,
): Promise<unknown> {
  return request(`/approve`, {
    method: "POST",
    body: JSON.stringify({ memo_id: memoId, section_key: sectionKey, comments }),
  });
}

export async function rejectSection(
  memoId: string,
  sectionKey: string,
  comments: string,
): Promise<unknown> {
  return request(`/reject`, {
    method: "POST",
    body: JSON.stringify({ memo_id: memoId, section_key: sectionKey, comments }),
  });
}

export async function finalizeMemo(memoId: string): Promise<unknown> {
  return request(`/finalize`, {
    method: "POST",
    body: JSON.stringify({ memo_id: memoId }),
  });
}

// --- ECL ---
export async function computeECL(): Promise<ECLResult> {
  return request<ECLResult>("/ecl/compute", { method: "POST" });
}

// --- Audit ---
export async function getAuditLog(memoId?: string): Promise<AuditLogEntry[]> {
  const q = memoId ? `?memo_id=${memoId}` : "";
  return request<AuditLogEntry[]>(`/audit-log${q}`);
}

// --- Reports ---
export async function getReports(): Promise<ReportSummary> {
  return request<ReportSummary>("/reports");
}
