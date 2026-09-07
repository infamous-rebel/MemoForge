export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: string;
}

export interface MemoSection {
  id: string;
  section_key: string;
  title: string;
  content: string;
  review_status: string;
  requires_review: boolean;
  review_reason: string;
  citations_json: Record<string, string> | null;
  flags_json: Record<string, unknown> | null;
}

export interface Memo {
  id: string;
  client_id: string;
  client_name: string;
  facility_type: string;
  deal_value: number;
  status: string;
  workflow_stage: string;
  sections: MemoSection[];
  created_at: string;
  metadata_json: Record<string, unknown> | null;
}

export interface WorkflowEvent {
  id: string;
  memo_id: string;
  section_key: string;
  action: string;
  user_id: string;
  timestamp: string;
  comments: string;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  user_id: string;
  memo_id: string;
  timestamp: string;
  payload_json: Record<string, unknown> | null;
  hash_chain: string;
}

export interface ECLResult {
  total_ecl: number;
  stage_1_ecl: number;
  stage_2_ecl: number;
  stage_3_ecl: number;
  facility_count: number;
  weighted_pd: number;
  weighted_lgd: number;
}

export interface GenerateMemoRequest {
  client_id: string;
  client_name: string;
  facility_type: string;
  deal_value: number;
}

export interface ReportSummary {
  report_type: string;
  generated_at: string;
  total_memos: number;
  approved_count: number;
  rejected_count: number;
  pending_count: number;
  avg_generation_time_seconds: number;
}

export type Role = "RM" | "Risk" | "CreditCommittee" | "ShariahBoard" | "Admin";

export interface User {
  user_id: string;
  role: Role;
  name: string;
  email: string;
}
