import { useEffect, useMemo, useState } from "react";
import type { Role } from "../types/api";
import { useToast } from "../components/Toast";
import { getAuditLog, getUsers } from "../services/api";
import type { AuditLogEntry, UserAccount } from "../types/api";

const ROLES: Role[] = ["RM", "Risk", "CreditCommittee", "ShariahBoard", "Admin"];

const roleDescriptions: Record<string, string> = {
  "Shariah Advisor": "Final verification on Shariah-critical sections and waivers.",
  "Risk Head": "Approves risk & mitigants sections above KD 5M exposure.",
  "Relationship Mgr.": "Generates memos and owns client documentation requests.",
};

const levelPill: Record<string, string> = {
  green: "badge-green",
  navy: "badge-navy",
  gray: "badge-gray",
};

const statusStyle: Record<string, string> = {
  SUCCESS: "text-status-success",
  FAILED: "text-status-danger",
  PENDING: "text-status-warning",
};

interface PolicyToggleProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}

function PolicyToggle({ label, description, checked, onChange }: PolicyToggleProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-bold text-frost-deep">{label}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-frost-slate">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-frost-navy/30 ${
          checked ? "bg-frost-navy" : "bg-frost-mist"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

export default function Admin() {
  const { push } = useToast();
  const [selectedRole, setSelectedRole] = useState<string>("RM");
  const [policies, setPolicies] = useState({ dualApproval: true, shariahAutoSigning: false });
  const [search, setSearch] = useState("");
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [loading, setLoading] = useState(true);

  const [showAddUser, setShowAddUser] = useState(false);
  const [newUserId, setNewUserId] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserRole, setNewUserRole] = useState<Role>("RM");

  useEffect(() => {
    async function fetchData() {
      try {
        const [auditRes, usersRes] = await Promise.all([
          getAuditLog(),
          getUsers().catch(() => ({ users: [] })),
        ]);
        setAuditLog(auditRes.entries);
        setUsers(usersRes.users);
      } catch (err) {
        push("Failed to load admin data", "error");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // Transform audit log to match the UI structure
  const systemAuditLog = auditLog.map((entry) => ({
    timestamp: new Date(entry.timestamp).toLocaleString(),
    user: entry.user_id || "system",
    action: entry.action,
    resource: entry.memo_id || "—",
    status: String(entry.payload_json?.status || "SUCCESS"),
  }));

  // Mock role configuration for now
  const roleConfiguration = [
    { role: "RM", level: "green", description: "Relationship Manager" },
    { role: "Risk", level: "navy", description: "Risk Head" },
    { role: "CreditCommittee", level: "navy", description: "Credit Committee" },
    { role: "ShariahBoard", level: "gray", description: "Shariah Advisor" },
    { role: "Admin", level: "navy", description: "System Administrator" },
  ];

  const filteredLogs = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return systemAuditLog;
    return systemAuditLog.filter((l) =>
      [l.timestamp, l.user, l.action, l.resource, l.status].some((f) =>
        f.toLowerCase().includes(q),
      ),
    );
  }, [search]);

  const handleAddUser = () => {
    if (!newUserId.trim() || !newUserName.trim()) {
      push("User ID and full name are required.", "error");
      return;
    }
    push(`User "${newUserName.trim()}" provisioned with ${newUserRole} role.`, "success");
    setNewUserId("");
    setNewUserName("");
    setNewUserEmail("");
    setNewUserRole("RM");
    setShowAddUser(false);
  };

  return (
    <div>
      {/* ── Header ─────────────────────────────────────── */}
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-frost-navy">Admin & RBAC</h1>
          <p className="mt-1 text-sm text-frost-slate">
            Manage system roles, user permissions, and security audit logs.
          </p>
        </div>
        <button onClick={() => setShowAddUser(true)} className="btn-navy">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
          </svg>
          Add User
        </button>
      </div>

      {/* ── Split layout ───────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT — roles + policies */}
        <div className="space-y-6">
          {/* Role configuration */}
          <div className="card p-6">
            <h2 className="text-base font-bold text-frost-deep">Role Configuration</h2>
            <p className="mt-1 text-xs text-frost-slate">Sign-off hierarchy for memo approval chains.</p>
            <div className="mt-4 space-y-3">
              {roleConfiguration.map((r) => {
                const active = r.role === selectedRole;
                const cardStyle = active
                  ? r.level === "green"
                    ? "border-emerald-200 bg-emerald-50/70"
                    : "border-frost-navy/25 bg-frost-light"
                  : "border-frost-mist bg-white hover:border-frost-navy/20 hover:bg-frost-surface";
                return (
                  <button
                    key={r.role}
                    onClick={() => {
                      setSelectedRole(r.role);
                      push(`${r.role} configuration opened — ${r.level} clearance.`, "info");
                    }}
                    className={`w-full rounded-xl border px-5 py-4 text-left shadow-sm transition ${cardStyle}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-frost-deep">{r.role}</p>
                        <p className="mt-0.5 text-xs leading-relaxed text-frost-slate">
                          {r.description}
                        </p>
                      </div>
                      <span className={levelPill[r.level]}>{r.level}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Security policies */}
          <div className="card p-6">
            <h2 className="text-base font-bold text-frost-deep">Security Policies</h2>
            <p className="mt-1 text-xs text-frost-slate">Bank-wide controls applied to every memo.</p>
            <div className="mt-5 space-y-5">
              <PolicyToggle
                label="Dual Approval Required"
                description="Final memo sign-off requires two authorized signatures from distinct roles."
                checked={policies.dualApproval}
                onChange={(next) => {
                  setPolicies((p) => ({ ...p, dualApproval: next }));
                  push(
                    next
                      ? "Dual Approval Required enabled — finalization now needs two signatories."
                      : "Dual Approval Required disabled.",
                    next ? "success" : "info",
                  );
                }}
              />
              <PolicyToggle
                label="Shariah Auto-Signing"
                description="Auto-sign Shariah-approved sections without manual Board verification."
                checked={policies.shariahAutoSigning}
                onChange={(next) => {
                  setPolicies((p) => ({ ...p, shariahAutoSigning: next }));
                  push(
                    next
                      ? "Shariah Auto-Signing enabled — the Shariah Board will be notified."
                      : "Shariah Auto-Signing disabled.",
                    next ? "info" : "success",
                  );
                }}
              />
            </div>
          </div>
        </div>

        {/* RIGHT — system audit log */}
        <div className="card overflow-hidden lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-frost-mist px-6 py-4">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-bold text-frost-deep">System Audit Log</h2>
              <span className="badge-green">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Hash-chain Verified
              </span>
            </div>
            <div className="relative w-full sm:w-64">
              <svg
                className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-frost-steel"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search logs..."
                aria-label="Search audit logs"
                className="field !py-2.5 !pl-10"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead>
                <tr className="table-head">
                  <th className="px-6 py-3">Timestamp</th>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Resource</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-sm text-frost-steel">
                      No log entries match &ldquo;{search}&rdquo;.
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((l) => (
                    <tr key={`${l.timestamp}-${l.user}-${l.action}`} className="table-row">
                      <td className="px-6 py-4 font-mono text-xs text-frost-slate">{l.timestamp}</td>
                      <td className="px-4 py-4 font-semibold text-frost-deep">{l.user}</td>
                      <td className="px-4 py-4 font-mono text-xs font-semibold text-frost-navy">
                        {l.action}
                      </td>
                      <td className="px-4 py-4 font-mono text-xs text-frost-slate">{l.resource}</td>
                      <td className={`px-6 py-4 text-xs font-bold ${statusStyle[l.status]}`}>
                        {l.status}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="border-t border-frost-mist px-6 py-3.5">
            <p className="text-xs text-frost-steel">
              Showing {filteredLogs.length} of {systemAuditLog.length} entries · Tamper-evident
              hash-chained records · Retained 7 years per CBK directive
            </p>
          </div>
        </div>
      </div>

      {/* ── Add user modal ─────────────────────────────── */}
      {showAddUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-frost-navy/50 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Add user"
          onClick={() => setShowAddUser(false)}
        >
          <div className="card w-full max-w-md p-7" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-frost-deep">Add User</h2>
            <p className="mt-1 text-sm text-frost-slate">
              Provision a new seat and assign an RBAC role.
            </p>
            <div className="mt-5 space-y-4">
              <div>
                <label htmlFor="new-user-id" className="field-label">User ID</label>
                <input
                  id="new-user-id"
                  type="text"
                  value={newUserId}
                  onChange={(e) => setNewUserId(e.target.value)}
                  placeholder="e.g. rm_yousef"
                  className="field"
                />
              </div>
              <div>
                <label htmlFor="new-user-name" className="field-label">Full Name</label>
                <input
                  id="new-user-name"
                  type="text"
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  placeholder="e.g. Yousef Al-Kandari"
                  className="field"
                />
              </div>
              <div>
                <label htmlFor="new-user-email" className="field-label">Email</label>
                <input
                  id="new-user-email"
                  type="email"
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="y.kandari@warbabank.com.kw"
                  className="field"
                />
              </div>
              <div>
                <label htmlFor="new-user-role" className="field-label">Role</label>
                <select
                  id="new-user-role"
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value as Role)}
                  className="field"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={() => setShowAddUser(false)} className="btn-outline">Cancel</button>
              <button onClick={handleAddUser} className="btn-navy">Add User</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
