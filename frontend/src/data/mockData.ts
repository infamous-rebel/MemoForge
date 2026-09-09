/**
 * Shared domain types and realistic mock data for the MemoForge UI.
 * When the backend is connected, these are progressively replaced by
 * live API responses; mock values mirror production-shaped data.
 */

export type WorkflowStage =
  | "Draft"
  | "Risk Review"
  | "Credit Committee"
  | "Shariah Board"
  | "Final Approval";

export type SlaStatus = "On Track" | "At Risk" | "Overdue";

export interface PipelineMemo {
  id: string;
  client: string;
  clientCode: string;
  facilityType: string;
  stage: WorkflowStage;
  slaStatus: SlaStatus;
  slaRemaining: string;
  dealValue: number;
  priority: "HIGH PRIORITY" | "STANDARD";
  assignedRole: string;
  assignedNote: string;
}

export const pipelineMemos: PipelineMemo[] = [
  {
    id: "MEM-2026-081",
    client: "Kuwait Tech Logix",
    clientCode: "KTL",
    facilityType: "Murabaha Facility",
    stage: "Risk Review",
    slaStatus: "On Track",
    slaRemaining: "22h remaining",
    dealValue: 1_250_000,
    priority: "HIGH PRIORITY",
    assignedRole: "Risk Manager (Lead)",
    assignedNote: "Awaiting financial ratio validation.",
  },
  {
    id: "MEM-2026-078",
    client: "Gulf Al-Oula Ltd",
    clientCode: "GA",
    facilityType: "Ijara Financing",
    stage: "Shariah Board",
    slaStatus: "At Risk",
    slaRemaining: "4h remaining",
    dealValue: 3_400_000,
    priority: "HIGH PRIORITY",
    assignedRole: "Shariah Advisor",
    assignedNote: "Prohibited-term review in progress.",
  },
  {
    id: "MEM-2026-075",
    client: "Beacon National",
    clientCode: "BN",
    facilityType: "Revolving Credit",
    stage: "Credit Committee",
    slaStatus: "On Track",
    slaRemaining: "3d remaining",
    dealValue: 900_000,
    priority: "STANDARD",
    assignedRole: "Credit Committee",
    assignedNote: "Quorum pending second approval.",
  },
  {
    id: "MEM-2026-069",
    client: "Amghara Industries",
    clientCode: "AI",
    facilityType: "Musharakah Facility",
    stage: "Draft",
    slaStatus: "On Track",
    slaRemaining: "5d remaining",
    dealValue: 5_600_000,
    priority: "STANDARD",
    assignedRole: "Relationship Manager",
    assignedNote: "Narrative generation queued.",
  },
  {
    id: "MEM-2026-062",
    client: "Sharq Holdings",
    clientCode: "SH",
    facilityType: "Sukuk Issuance",
    stage: "Risk Review",
    slaStatus: "Overdue",
    slaRemaining: "+18h overdue",
    dealValue: 12_000_000,
    priority: "HIGH PRIORITY",
    assignedRole: "Risk Manager",
    assignedNote: "Escalation triggered by SLA monitor.",
  },
];

export interface ComplianceAlert {
  kind: "SHARIAH FLAG" | "CITATION ISSUE" | "POLICY EXCEPTION";
  memoId: string;
  detail: string;
  action: string;
  when: string;
}

export const complianceAlerts: ComplianceAlert[] = [
  {
    kind: "SHARIAH FLAG",
    memoId: "MEM-2026-078",
    detail: "Clause 4.2 in MEM-2026-078 contains prohibited profit-sharing terms.",
    action: "Review Now",
    when: "Just now",
  },
  {
    kind: "CITATION ISSUE",
    memoId: "MEM-2026-081",
    detail: "Internal Policy BP-2024 citation is outdated in MEM-2026-081.",
    action: "Update Citation",
    when: "2h ago",
  },
  {
    kind: "POLICY EXCEPTION",
    memoId: "MEM-2026-062",
    detail: "Single-name exposure exceeds 10% of Tier 1 capital in MEM-2026-062.",
    action: "Review Now",
    when: "1d ago",
  },
];

export const eclSummary = {
  memoforgeEcl: 1_420_000,
  warbaActuals: 1_390_000,
  stages: [
    { name: "Stage 1", label: "Low Risk", value: 890_000, facilities: 31 },
    { name: "Stage 2", label: "Inc. Risk", value: 390_000, facilities: 12 },
    { name: "Stage 3", label: "Impaired", value: 142_000, facilities: 5 },
  ],
  provisionCoverage: 0.926,
  totalExposure: 48_600_000,
};

export interface ECLFacility {
  id: string;
  client: string;
  facilityType: string;
  exposure: number;
  stage: 1 | 2 | 3;
  pd: number;
  lgd: number;
  ecl: number;
  rule: string;
}

export const eclFacilities: ECLFacility[] = [
  {
    id: "FAC-1041",
    client: "Kuwait Tech Logix",
    facilityType: "Murabaha",
    exposure: 1_250_000,
    stage: 1,
    pd: 0.012,
    lgd: 0.4,
    ecl: 6_240,
    rule: "Stage 1 · 12-month ECL · PD floor 1%",
  },
  {
    id: "FAC-1038",
    client: "Gulf Al-Oula Ltd",
    facilityType: "Ijara",
    exposure: 3_400_000,
    stage: 2,
    pd: 0.048,
    lgd: 0.45,
    ecl: 88_560,
    rule: "Stage 2 · Lifetime ECL · SICR trigger: 30+ DPD",
  },
  {
    id: "FAC-1030",
    client: "Sharq Holdings",
    facilityType: "Sukuk",
    exposure: 12_000_000,
    stage: 2,
    pd: 0.055,
    lgd: 0.35,
    ecl: 462_000,
    rule: "Stage 2 · Lifetime ECL · Rating migration",
  },
  {
    id: "FAC-1022",
    client: "Amghara Industries",
    facilityType: "Musharakah",
    exposure: 5_600_000,
    stage: 3,
    pd: 1.0,
    lgd: 0.28,
    ecl: 331_520,
    rule: "Stage 3 · Impaired · Collateral-adjusted LGD",
  },
  {
    id: "FAC-1017",
    client: "Beacon National",
    facilityType: "Tawarruq",
    exposure: 900_000,
    stage: 1,
    pd: 0.01,
    lgd: 0.5,
    ecl: 4_500,
    rule: "Stage 1 · 12-month ECL · PD floor applied",
  },
];

export interface ReviewSection {
  num: string;
  title: string;
  status: "SECTION APPROVED" | "PENDING REVIEW" | "LOCKED";
  infoBanner?: string;
  body: string;
  exception?: {
    title: string;
    detail: string;
  };
  metrics?: { label: string; value: string; delta?: string }[];
  citation?: string;
  roleRestriction?: string;
}

export const reviewSections: ReviewSection[] = [
  {
    num: "01",
    title: "Borrower Overview",
    status: "SECTION APPROVED",
    infoBanner:
      "Auto-generated via Compliance Agent. Validation data pulled from Kuwait Chamber of Commerce (API-88).",
    body: "Kuwait Tech Logix (KTL) is a digital infrastructure provider in MENA, specializing in hyper-scale data centers and sovereign cloud solutions. Established 2014, the company has delivered a 22% revenue CAGR over three years. KTL operates under Al-Sabah Holding Group and its strategy is aligned with Kuwait's Vision 2035 digital transformation agenda. [ref:chunk_001]",
  },
  {
    num: "02",
    title: "Financial Analysis",
    status: "PENDING REVIEW",
    exception: {
      title: "SHARIAH EXCEPTION DETECTED",
      detail:
        "Debt-to-Equity ratio (38%) slightly exceeds 33.3% threshold. Requires mitigation section analysis or Shariah Board waiver.",
    },
    metrics: [
      { label: "EBITDA MARGIN", value: "34.2%", delta: "+2.1%" },
      { label: "QUICK RATIO", value: "1.82x" },
    ],
    body: "Current analysis indicates robust cash flow generation from the Infrastructure Services segment, which accounts for 60% of total revenue. Debt service coverage of 1.44x remains above the 1.2x policy floor, while leverage of 2.02x sits within the 3.0x maximum. [ref:chunk_003]",
    citation: "[2] Q3 FY2026 internal audit pack, p.14",
  },
  {
    num: "03",
    title: "Risk & Mitigants",
    status: "LOCKED",
    roleRestriction:
      "Role Restriction — Only users with 'Head of Risk' role can review this section.",
    body: "",
  },
];

export const reviewWorkflow = [
  { role: "Relationship Manager", state: "COMPLETED", meta: "Mar 14, 10:20 AM", kind: "done" },
  { role: "Risk Management", state: "IN PROGRESS", meta: "Started 4h ago", kind: "active" },
  { role: "Credit Committee", state: "PENDING APPROVAL", meta: "", kind: "pending" },
  { role: "Shariah Review", state: "FINAL VERIFICATION", meta: "", kind: "pending" },
] as const;

export const auditTrail = [
  {
    when: "2h ago",
    who: "Ahmad Al-Farsi (RM)",
    what: "Attached updated segmental revenue for KTL. Financials now reflect Q3 internal audit.",
  },
  {
    when: "3h ago",
    who: "System Agent (Compiler)",
    what: "Section 'Borrower Overview' validated and auto-signed.",
  },
  {
    when: "5h ago",
    who: "System Agent (Data)",
    what: "Retrieved 14 ACL-filtered document chunks from core banking vault.",
  },
];

export interface PerformanceLog {
  type: "CRITICAL BREACH" | "WARNING";
  memoId: string;
  stage: string;
  assignedTo: string;
  delay: string;
  action: "ESCALATE" | "REVIEW";
}

export const slaViolations: PerformanceLog[] = [
  {
    type: "CRITICAL BREACH",
    memoId: "MEM-2026-062",
    stage: "Risk Review",
    assignedTo: "J. Smith (RM)",
    delay: "+18h 12m",
    action: "ESCALATE",
  },
  {
    type: "WARNING",
    memoId: "MEM-2026-078",
    stage: "Shariah Audit",
    assignedTo: "F. Rashid",
    delay: "+2h 05m",
    action: "REVIEW",
  },
  {
    type: "WARNING",
    memoId: "MEM-2026-059",
    stage: "Credit Committee",
    assignedTo: "Committee Quorum",
    delay: "+1h 40m",
    action: "REVIEW",
  },
];

export const approvalDelays: PerformanceLog[] = [
  {
    type: "WARNING",
    memoId: "MEM-2026-081",
    stage: "Risk Review",
    assignedTo: "K. Al-Anzi (Risk)",
    delay: "+6h 30m",
    action: "REVIEW",
  },
  {
    type: "CRITICAL BREACH",
    memoId: "MEM-2026-055",
    stage: "Final Approval",
    assignedTo: "Dual Signatories",
    delay: "+26h 00m",
    action: "ESCALATE",
  },
];

export const pipelineStatus = [
  { name: "Approved", value: 18, color: "#0F2A4A" },
  { name: "In Review", value: 9, color: "#64748B" },
  { name: "Draft", value: 4, color: "#C9A227" },
];

export interface SystemAuditEntry {
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  status: "SUCCESS" | "FAILED" | "PENDING";
}

export const systemAuditLog: SystemAuditEntry[] = [
  { timestamp: "2026-03-14 14:22:05", user: "A. Farsi", action: "UPDATE_SECTION", resource: "MEM-2026-081", status: "SUCCESS" },
  { timestamp: "2026-03-14 13:10:42", user: "System", action: "ESCALATION_TRIGGER", resource: "MEM-2026-062", status: "SUCCESS" },
  { timestamp: "2026-03-14 11:05:18", user: "F. Rashid", action: "REJECT_MEMO", resource: "MEM-2026-078", status: "SUCCESS" },
  { timestamp: "2026-03-14 09:58:03", user: "S. Al-Mutairi", action: "LOGIN", resource: "SESSION-4471", status: "SUCCESS" },
  { timestamp: "2026-03-13 17:44:29", user: "M. Al-Otaibi", action: "APPROVE_SECTION", resource: "MEM-2026-075", status: "SUCCESS" },
  { timestamp: "2026-03-13 16:12:51", user: "Unknown", action: "LOGIN", resource: "SESSION-4468", status: "FAILED" },
];

export const roleConfiguration = [
  { role: "Shariah Advisor", level: "LvL 4", active: true, color: "green" },
  { role: "Risk Head", level: "LvL 4", active: false, color: "navy" },
  { role: "Relationship Mgr.", level: "LvL 2", active: false, color: "gray" },
] as const;

export function formatKD(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `KD ${(value / 1_000_000).toFixed(2)}M`;
  }
  return `KD ${value.toLocaleString()}`;
}
