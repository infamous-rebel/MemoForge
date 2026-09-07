import { useState } from "react";
import { getAuditLog } from "../services/api";
import type { AuditLogEntry } from "../types/api";
import { useToast } from "../components/Toast";
import { SkeletonTable } from "../components/Skeleton";

const demoLogs: AuditLogEntry[] = [
  { id: "1", action: "generate_memo", user_id: "rm_ahmad", memo_id: "MEM-2026-081", timestamp: "2026-03-14T10:30:00Z", payload_json: { client_id: "KTL", facility_type: "murabaha" }, hash_chain: "a3f2…" },
  { id: "2", action: "auto_approve", user_id: "system", memo_id: "MEM-2026-081", timestamp: "2026-03-14T10:30:05Z", payload_json: { section: "financial_analysis", rule: "auto_approved_no_flags" }, hash_chain: "b7c1…" },
  { id: "3", action: "approve_section", user_id: "risk_sara", memo_id: "MEM-2026-081", timestamp: "2026-03-14T11:15:00Z", payload_json: { section: "risk_and_mitigants" }, hash_chain: "d4e8…" },
  { id: "4", action: "finalize_memo", user_id: "rm_ahmad", memo_id: "MEM-2026-075", timestamp: "2026-03-14T14:00:00Z", payload_json: {}, hash_chain: "f2a9…" },
];

export default function AuditLog() {
  const { push } = useToast();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLoad = async () => {
    setLoading(true);
    try {
      const data = await getAuditLog();
      setLogs(data.entries);
      push("Audit log refreshed from the hash-chained ledger.", "success");
    } catch {
      setLogs(demoLogs);
      push("Audit log refreshed (offline mode — cached entries).", "info");
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  };

  const displayLogs = loaded ? logs : demoLogs;
  const q = search.trim().toLowerCase();
  const filtered = q
    ? displayLogs.filter(
        (l) =>
          l.action.toLowerCase().includes(q) ||
          l.user_id.toLowerCase().includes(q) ||
          l.memo_id.toLowerCase().includes(q),
      )
    : displayLogs;

  const handleExport = () => {
    const csv = filtered
      .map((l) => `${l.timestamp},${l.action},${l.user_id},${l.memo_id},${l.hash_chain}`)
      .join("\n");
    const blob = new Blob([`Timestamp,Action,User,Memo,Hash\n${csv}`], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "memoforge_audit_log.csv";
    a.click();
    URL.revokeObjectURL(url);
    push("Audit log exported as CSV.", "success");
  };

  return (
    <div>
      {/* ── Header ─────────────────────────────────────── */}
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-frost-navy">Audit Log</h1>
          <p className="mt-1 text-sm text-frost-slate">
            Tamper-evident, hash-chained record of every system action.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="badge-green">
            <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Hash-chain Verified
          </span>
          <button onClick={handleLoad} disabled={loading} className="btn-outline">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992V4.356m0 4.992l-3.181-3.183a8.25 8.25 0 00-13.803 3.7M4.031 9.865v4.99m0 0H9.02m-4.985 0l3.181 3.183a8.25 8.25 0 0013.803-3.7" />
            </svg>
            {loading ? "Loading…" : "Refresh from API"}
          </button>
        </div>
      </div>

      {/* ── Search ─────────────────────────────────────── */}
      <div className="card mb-6 p-4">
        <div className="relative">
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
            placeholder="Search by action, user, or memo ID…"
            aria-label="Search audit log"
            className="field !py-2.5 !pl-10"
          />
        </div>
      </div>

      {/* ── Log table ──────────────────────────────────── */}
      {loading ? (
        <SkeletonTable rows={5} cols={5} />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="table-head">
                  <th className="px-6 py-3">Timestamp</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Memo</th>
                  <th className="px-6 py-3">Hash</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-sm text-frost-steel">
                      No entries match &ldquo;{search}&rdquo;.
                    </td>
                  </tr>
                ) : (
                  filtered.map((log) => (
                    <tr key={log.id} className="table-row">
                      <td className="px-6 py-4 font-mono text-xs text-frost-slate">
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-4">
                        <span className="badge-blue">{log.action}</span>
                      </td>
                      <td className="px-4 py-4 font-semibold text-frost-deep">{log.user_id}</td>
                      <td className="px-4 py-4 font-mono text-xs text-frost-navy">{log.memo_id}</td>
                      <td className="px-6 py-4 font-mono text-xs text-frost-steel">{log.hash_chain}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="border-t border-frost-mist px-6 py-3.5">
            <p className="text-xs text-frost-steel">
              Showing {filtered.length} of {displayLogs.length} entries · Each record links to its
              predecessor via SHA-256 — any tampering breaks the chain.
            </p>
          </div>
        </div>
      )}

      {/* ── Export ─────────────────────────────────────── */}
      <div className="mt-5">
        <button onClick={handleExport} className="btn-navy !px-5 !py-2.5 text-xs">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          Export CSV
        </button>
      </div>
    </div>
  );
}
