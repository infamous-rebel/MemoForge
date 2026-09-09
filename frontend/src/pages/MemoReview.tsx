import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { approveSection, rejectSection, finalizeMemo, getMemo, getMemoAuditLog } from "../services/api";
import { useToast } from "../components/Toast";
import type { Memo, AuditLogEntry } from "../types/api";

function useCountdown(initialSeconds: number) {
  const [seconds, setSeconds] = useState(initialSeconds);
  useEffect(() => {
    const t = window.setInterval(() => setSeconds((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => window.clearInterval(t);
  }, []);
  const hh = String(Math.floor(seconds / 3600)).padStart(2, "0");
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

const statusBadge: Record<string, string> = {
  "SECTION APPROVED": "badge-green",
  "PENDING REVIEW": "badge-amber",
  LOCKED: "badge-gray",
};

const workflowIcon: Record<string, { icon: string; className: string }> = {
  done: { icon: "✓", className: "bg-status-success text-white" },
  active: { icon: "●", className: "bg-status-warning text-white" },
  pending: { icon: "○", className: "border-2 border-frost-mist bg-white text-frost-steel" },
};

export default function MemoReview() {
  const { memoId } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const role = localStorage.getItem("role") || "RM";
  const canApprove = ["RM", "Risk", "CreditCommittee", "ShariahBoard", "Admin"].includes(role);

  const [memo, setMemo] = useState<Memo | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [approved, setApproved] = useState<Record<string, boolean>>({});
  const [rejected, setRejected] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function fetchData() {
      if (!memoId) return;
      try {
        const [memoRes, auditRes] = await Promise.all([
          getMemo(memoId),
          getMemoAuditLog(memoId).catch(() => ({ entries: [] })),
        ]);
        setMemo(memoRes);
        setAuditEntries(auditRes.entries);
      } catch (err) {
        push("Failed to load memo", "error");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [memoId]);

  const reviewSections = memo?.sections || [];
  const auditTrail = auditEntries;

  // Mock workflow based on memo status
  const reviewWorkflow = memo
    ? [
        { role: "Relationship Manager", kind: "done" as const, state: "SUBMITTED", meta: "Initial submission" },
        { role: "Risk Manager", kind: memo.workflow_stage === "risk_review" ? "active" as const : "pending" as const, state: memo.workflow_stage === "risk_review" ? "REVIEWING" : "PENDING" },
        { role: "Credit Committee", kind: "pending" as const, state: "PENDING" },
        { role: "Shariah Board", kind: "pending" as const, state: "PENDING" },
      ]
    : [];

  const handleApprove = async (sectionKey: string) => {
    try {
      await approveSection(memoId ?? "", sectionKey, comments[sectionKey] ?? "");
      push(`Section approved.`, "success");
      setApproved((prev) => ({ ...prev, [sectionKey]: true }));
      setRejected((prev) => ({ ...prev, [sectionKey]: false }));
      setComments((prev) => ({ ...prev, [sectionKey]: "" }));
    } catch {
      push(`Failed to approve section. Please try again.`, "error");
    }
  };

  const handleReject = async (sectionKey: string) => {
    try {
      await rejectSection(memoId ?? "", sectionKey, comments[sectionKey] ?? "");
      push(`Section rejected with comment.`, "error");
      setRejected((prev) => ({ ...prev, [sectionKey]: true }));
      setApproved((prev) => ({ ...prev, [sectionKey]: false }));
      setComments((prev) => ({ ...prev, [sectionKey]: "" }));
    } catch {
      push(`Failed to reject section. Please try again.`, "error");
    }
  };

  const handleFinalize = async () => {
    try {
      await finalizeMemo(memoId ?? "");
      push("Memo finalized — compiled document archived.", "success");
    } catch {
      push("Failed to finalize memo. Please try again.", "error");
    }
  };

  const effectiveStatus = (s: (typeof reviewSections)[number]) => {
    if (approved[s.section_key]) return "SECTION APPROVED";
    if (rejected[s.section_key]) return "LOCKED";
    return s.review_status === "auto_approved" ? "SECTION APPROVED" : s.review_status === "pending" ? "PENDING REVIEW" : s.review_status.toUpperCase();
  };

  return (
    <div>
      {/* ── Top bar ─────────────────────────────────────── */}
      <div className="mb-7 flex items-center justify-between">
        <Link to="/dashboard" className="btn-ghost !px-3 text-frost-slate">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Back to Dashboard
        </Link>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-frost-mist bg-white py-1.5 pl-3 pr-4">
            <span className="h-2 w-2 rounded-full bg-status-success" />
            <span className="text-xs font-bold text-frost-navy">{role} — Risk Mode</span>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-frost-navy font-display text-sm font-bold text-gold">
            {(localStorage.getItem("user_id") || "A").charAt(0).toUpperCase()}
          </div>
        </div>
      </div>

      {/* ── Header ──────────────────────────────────────── */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold text-frost-navy">
          #{(memoId ?? "MEM-2026-081").replace(/^#/, "")}: Kuwait Tech Logix
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="badge-navy">Murabaha Facility</span>
          <span className="badge-green">Shariah Approved</span>
          <span className="badge-gray">KD 1,250,000</span>
        </div>
      </div>

      {/* ── Split view ──────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* LEFT — sections */}
        <div className="space-y-6 xl:col-span-2">
          {reviewSections.map((s, idx) => {
            const status = effectiveStatus(s);
            const locked = status === "LOCKED" && !!s.roleRestriction;
            return (
              <article key={s.section_key} className={`card p-7 ${locked ? "opacity-75" : ""}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-baseline gap-4">
                    <span className="font-display text-3xl font-bold text-frost-mist">{String(idx + 1).padStart(2, "0")}</span>
                    <h2 className="text-xl font-bold text-frost-deep">{s.title}</h2>
                  </div>
                  <span className={statusBadge[status] || "badge-gray"}>{status}</span>
                </div>

                {/* Role restriction (locked) */}
                {locked && s.roleRestriction && (
                  <div className="mt-5 flex items-start gap-3 rounded-xl border border-frost-mist bg-frost-light px-5 py-4 text-sm text-frost-slate">
                    <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                    {s.roleRestriction}
                  </div>
                )}

                {/* Info banner */}
                {s.infoBanner && (
                  <div className="mt-5 flex items-start gap-3 rounded-xl bg-blue-50/70 px-5 py-3.5 text-sm text-blue-800">
                    <svg className="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.852l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
                    </svg>
                    {s.infoBanner}
                  </div>
                )}

                {/* Exception banner */}
                {s.exception && !locked && (
                  <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-5 py-4">
                    <div className="flex items-center gap-2">
                      <svg className="h-5 w-5 text-status-danger" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                      </svg>
                      <p className="text-xs font-bold uppercase tracking-wider text-status-danger">
                        {s.exception.title}
                      </p>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-red-800">{s.exception.detail}</p>
                    <button
                      onClick={() => push("Shariah exception routed to Shariah Board queue.", "info")}
                      className="btn-navy mt-3 !px-4 !py-2 text-xs"
                    >
                      Resolve Flag
                    </button>
                  </div>
                )}

                {/* Metrics */}
                {s.metrics && !locked && (
                  <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
                    {s.metrics.map((m) => (
                      <div key={m.label} className="rounded-xl bg-frost-light px-5 py-4">
                        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-frost-steel">{m.label}</p>
                        <p className="mt-1.5 flex items-baseline gap-2">
                          <span className="font-display text-2xl font-bold text-frost-navy">{m.value}</span>
                          {m.delta && (
                            <span className="text-xs font-bold text-status-success">↑ {m.delta}</span>
                          )}
                        </p>
                      </div>
                    ))}
                    <div className="rounded-xl bg-frost-light px-5 py-4">
                      <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-frost-steel">DSCR</p>
                      <p className="mt-1.5 font-display text-2xl font-bold text-frost-navy">1.44x</p>
                    </div>
                  </div>
                )}

                {/* Body */}
                {s.body ? (
                  <p className="mt-5 text-sm leading-relaxed text-frost-slate">{s.body}</p>
                ) : (
                  <p className="mt-5 text-sm leading-relaxed text-frost-slate">{s.content}</p>
                )}

                {/* Citation */}
                {s.citation && (
                  <p className="mt-3 font-mono text-xs text-frost-steel">{s.citation}</p>
                )}

                {/* Review controls */}
                {!locked && (s.body || s.content) && (
                  <div className="mt-6 border-t border-frost-mist pt-5">
                    <label className="field-label">Review Comment</label>
                    <textarea
                      rows={2}
                      value={comments[s.section_key] ?? ""}
                      onChange={(e) => setComments((prev) => ({ ...prev, [s.section_key]: e.target.value }))}
                      placeholder="Add a review comment…"
                      className="field !py-2.5"
                    />
                    {canApprove && (
                      <div className="mt-4 flex flex-wrap gap-3">
                        <button
                          onClick={() => handleApprove(s.section_key)}
                          disabled={!!approved[s.section_key]}
                          className="btn-navy !px-5 !py-2.5 text-xs"
                        >
                          {approved[s.section_key] ? "✓ Approved" : "{section.review_status === "approved" ? "Approved" : "Approve Section"}"}
                        </button>
                        <button
                          onClick={() => handleReject(s.section_key)}
                          className="btn-outline !px-5 !py-2.5 text-xs !text-status-danger hover:!border-red-200 hover:!bg-red-50"
                        >
                          Reject with Comment
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>

        {/* RIGHT — status / audit / actions */}
        <div className="space-y-6">
          {/* Review Status */}
          <div className="card p-6">
            <h2 className="text-base font-bold text-frost-deep">Review Status</h2>
            <ol className="mt-5 space-y-5">
              {reviewWorkflow.map((w) => {
                const icon = workflowIcon[w.kind];
                return (
                  <li key={w.role} className="relative flex items-start gap-4 pb-5 last:pb-0">
                    <div className="absolute bottom-0 left-[15px] top-9 w-px bg-frost-mist last:hidden" />
                    <div className={`z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${icon.className}`}>
                      {icon.icon}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-frost-deep">{w.role}</p>
                      <p
                        className={`mt-0.5 text-[11px] font-bold uppercase tracking-wide ${
                          w.kind === "done"
                            ? "text-status-success"
                            : w.kind === "active"
                              ? "text-status-warning"
                              : "text-frost-steel"
                        }`}
                      >
                        {w.state}
                        {w.meta ? ` · ${w.meta}` : ""}
                      </p>
                      {w.kind === "active" && memo?.sla_status === "At Risk" && (
                        <div className="mt-2 inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5">
                          <span className="text-[10px] font-bold uppercase tracking-wide text-status-danger">
                            SLA At Risk
                          </span>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>

            <div className="mt-2 border-t border-frost-mist pt-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold uppercase tracking-wider text-frost-steel">
                  Committee Quorum
                </p>
                <p className="text-sm font-bold text-frost-deep">0/2 Approvals</p>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-frost-slate">
                Requires dual final approval from Risk Head and Shariah Advisor.
              </p>
            </div>
          </div>

          {/* Audit Trail */}
          <div className="card p-6">
            <h2 className="text-base font-bold text-frost-deep">Audit Trail</h2>
            <ol className="mt-5 space-y-4">
              {auditTrail.map((a, idx) => (
                <li key={a.id || idx} className="flex gap-3.5">
                  <div className="mt-1 flex h-2.5 w-2.5 shrink-0 rounded-full bg-frost-navy ring-4 ring-frost-navy/10" />
                  <div>
                    <div className="flex items-baseline gap-2">
                      <p className="text-sm font-semibold text-frost-deep">{a.user_id || "system"}</p>
                      <span className="text-[10px] text-frost-steel">{new Date(a.timestamp).toLocaleString()}</span>
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-frost-slate">{a.action}</p>
                  </div>
                </li>
              ))}
            </ol>
            <button
              onClick={() => navigate("/audit")}
              className="btn-outline mt-5 w-full !py-2.5 text-xs"
            >
              View Full Log
            </button>
          </div>

          {/* Actions */}
          <div className="card space-y-3 p-6">
            <button
              onClick={handleFinalize}
              className="btn-navy w-full py-3.5"
              disabled={!canApprove}
            >
              ✓ Finalize Memo
            </button>
            <p className="text-center text-xs text-frost-steel">
              Finalize will be enabled once all 5 sections are approved.
            </p>
            <button
              onClick={() => push("Memo escalated to Credit Committee.", "info")}
              className="btn-danger w-full !py-3 text-xs"
            >
              ▲ Escalate Memo
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
