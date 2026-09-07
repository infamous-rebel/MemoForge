import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { useToast } from "../components/Toast";
import { pipelineStatus, slaViolations, approvalDelays } from "../data/mockData";

const violationBadge: Record<string, string> = {
  "CRITICAL BREACH": "bg-red-100 text-red-700",
  WARNING: "bg-amber-100 text-amber-700",
};

type Tab = "SLA VIOLATIONS" | "APPROVAL DELAYS";

export default function Reports() {
  const { push } = useToast();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("SLA VIOLATIONS");

  const logs = tab === "SLA VIOLATIONS" ? slaViolations : approvalDelays;
  const totalPipeline = pipelineStatus.reduce((s, p) => s + p.value, 0);

  const handleExport = () => {
    const header = "Violation Type,Memo ID,Stage,Assigned To,Delay Duration,Action";
    const rows = logs.map((l) => `${l.type},${l.memoId},${l.stage},${l.assignedTo},${l.delay},${l.action}`);
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `memoforge_${tab.toLowerCase().replace(" ", "_")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    push(`${tab} report exported as CSV.`, "success");
  };

  return (
    <div>
      {/* ── Header ─────────────────────────────────────── */}
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-frost-navy">Reporting Center</h1>
          <p className="mt-1 text-sm text-frost-slate">
            Operational intelligence, SLA performance, and regulatory summaries.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-outline" title="Reporting period">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
            </svg>
            Last 30 Days
          </button>
          <button onClick={handleExport} className="btn-navy">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Export Center
          </button>
        </div>
      </div>

      {/* ── Metric cards ───────────────────────────────── */}
      <div className="mb-7 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {/* Pipeline status donut */}
        <div className="card p-6">
          <p className="text-xs font-bold uppercase tracking-wider text-frost-steel">Pipeline Status</p>
          <div className="mt-3 flex items-center gap-6">
            <div className="h-32 w-32 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pipelineStatus}
                    cx="50%"
                    cy="50%"
                    innerRadius={34}
                    outerRadius={55}
                    dataKey="value"
                    stroke="none"
                  >
                    {pipelineStatus.map((p, i) => (
                      <Cell key={i} fill={p.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number, name: string) => [`${v} memos`, name]}
                    contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0", fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="space-y-2.5">
              {pipelineStatus.map((p) => (
                <li key={p.name} className="flex items-center gap-2.5 text-sm">
                  <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: p.color }} />
                  <span className="text-frost-slate">{p.name}</span>
                  <span className="ml-auto font-bold text-frost-deep">{p.value}</span>
                </li>
              ))}
              <li className="border-t border-frost-mist pt-2 text-xs text-frost-steel">
                {totalPipeline} total memos
              </li>
            </ul>
          </div>
        </div>

        {/* SLA breach risk */}
        <div className="card flex flex-col justify-center p-6">
          <p className="text-xs font-bold uppercase tracking-wider text-frost-steel">SLA Breach Risk</p>
          <p className="mt-3 font-display text-5xl font-bold text-status-warning">12%</p>
          <p className="mt-2 text-sm text-frost-slate">Memos nearing escalation</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-frost-mist">
            <div className="h-full w-[12%] rounded-full bg-status-warning" />
          </div>
        </div>

        {/* Avg approval time */}
        <div className="card flex flex-col justify-center p-6">
          <p className="text-xs font-bold uppercase tracking-wider text-frost-steel">Avg. Approval Time</p>
          <p className="mt-3 font-display text-5xl font-bold text-frost-navy">4.2d</p>
          <p className="mt-2 text-sm text-frost-slate">Target: 3.5 days</p>
          <div className="mt-4 flex items-center gap-2 text-xs font-semibold text-status-warning">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
            </svg>
            0.7d above target
          </div>
        </div>
      </div>

      {/* ── Performance logs ───────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-frost-mist px-6 py-4">
          <h2 className="text-lg font-bold text-frost-deep">Performance Logs</h2>
          <div className="flex gap-1 rounded-xl bg-frost-light p-1">
            {(["SLA VIOLATIONS", "APPROVAL DELAYS"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-lg px-4 py-2 text-xs font-bold tracking-wide transition ${
                  tab === t ? "bg-frost-navy text-white shadow-card" : "text-frost-slate hover:text-frost-navy"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="table-head">
                <th className="px-6 py-3">Violation Type</th>
                <th className="px-4 py-3">Memo ID</th>
                <th className="px-4 py-3">Stage</th>
                <th className="px-4 py-3">Assigned To</th>
                <th className="px-4 py-3">Delay Duration</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={`${l.memoId}-${l.type}`} className="table-row">
                  <td className="px-6 py-4">
                    <span className={`badge ${violationBadge[l.type]}`}>{l.type}</span>
                  </td>
                  <td className="px-4 py-4 font-mono text-xs font-semibold text-frost-navy">{l.memoId}</td>
                  <td className="px-4 py-4 text-frost-slate">{l.stage}</td>
                  <td className="px-4 py-4 text-frost-deep">{l.assignedTo}</td>
                  <td className="px-4 py-4 font-mono text-xs font-bold text-status-warning">{l.delay}</td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => {
                        if (l.action === "ESCALATE") {
                          push(`${l.memoId} escalated to senior reviewer.`, "info");
                        } else {
                          navigate(`/review/${l.memoId.replace("#", "").replace("#", "")}`);
                        }
                      }}
                      className="text-xs font-bold uppercase tracking-wide text-frost-navy underline decoration-gold decoration-2 underline-offset-4 transition hover:text-gold"
                    >
                      {l.action}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t border-frost-mist px-6 py-3.5">
          <p className="text-xs text-frost-steel">
            Showing {logs.length} entries · Auto-refreshed every 15 minutes
          </p>
        </div>
      </div>
    </div>
  );
}
