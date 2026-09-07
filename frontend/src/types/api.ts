export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: string;
  full_name: string;
  username: string;
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
  // Optional fields from mock data (may not be in API)
  roleRestriction?: string;
  infoBanner?: string;
  exception?: { title: string; detail: string };
  metrics?: Array<{ label: string; value: string; delta?: string }>;
  body?: string;
  citation?: string;
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
  created_by: string;
  finalized_at: string | null;
  output_file_path: string | null;
  metadata_json: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  sla_status?: "On Track" | "At Risk" | "Overdue" | null;
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
  stage1_ecl: number;
  stage2_ecl: number;
  stage3_ecl: number;
  provision_coverage_ratio: number;
  stage_breakdown: Array<{
    stage: number;
    facility_count: number;
    total_ead: number;
    total_ecl: number;
    facilities: Array<{
      facility_id: string;
      stage: number;
      ead: number;
      pd: number;
      lgd: number;
      ecl: number;
      rules_applied: string[];
    }>;
  }>;
}

export interface GenerateMemoRequest {
  client_id: string;
  client_name: string;
  facility_type: string;
  deal_value: number;
}

export interface GenerateMemoResponse {
  memo_id: string;
  status: string;
  sections: Array<{
    section_key: string;
    title: string;
    review_status: string;
    requires_review: boolean;
    review_reason: string;
    auto_approved_rule: string | null;
  }>;
  workflow_stage: string;
}

export interface ReportSummary {
  report_type: string;
  format: string;
  generated_at: string;
  summary: {
    report_type: string;
    total_memos: number;
    avg_approval_hours?: number | null;
    total_delays?: number;
    active_escalations?: number;
  };
  content: string; // JSON string — parse for detailed data
}

export interface MemoListItem {
  id: string;
  client_id: string;
  client_name: string;
  facility_type: string;
  deal_value: number;
  status: string;
  workflow_stage: string;
  created_by: string;
  created_at: string;
  finalized_at: string | null;
  section_count: number;
  pending_review_count: number;
  shariah_flag_count: number;
  citation_flag_count: number;
  sla_status: "On Track" | "At Risk" | "Overdue" | null;
  sla_hours_remaining: number | null;
}

export interface NotificationItem {
  id: string;
  event_type: string;
  memo_id: string | null;
  subject: string;
  body: string;
  channel: string;
  status: string;
  sent_at: string;
  timestamp: string;
  read_at?: string | null;
  recipient?: string | null;
  client_name?: string | null;
}

export interface EscalationItem {
  id: string;
  memo_id: string;
  client_name: string | null;
  escalation_level: number;
  escalation_reason: string;
  sla_breach_pct: number;
  stage?: string;
  level?: string;
  recipient?: string;
  status?: string;
  created_at: string;
  resolved_at: string | null;
}

export interface UserAccount {
  id: string;
  username: string;
  full_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface ClientProfile {
  client_id: string;
  client_name: string;
  facility_type: string;
  deal_value: number;
  risk_rating: string;
}

export type Role = "RM" | "Risk" | "CreditCommittee" | "ShariahBoard" | "Admin";

export interface User {
  user_id: string;
  role: Role;
  name: string;
  email: string;
}
