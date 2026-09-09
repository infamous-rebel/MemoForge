import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { useToast } from "../components/Toast";
import { SkeletonTable } from "../components/Skeleton";
import { getMemos, computeECL } from "../services/api";
import type { MemoListItem, ECLResult } from "../types/api";
import { formatKD } from "../data/mockData";

type SlaStatus = "On Track" | "At Risk" | "Overdue";
type WorkflowStage = string;

const kpis = [
  {
    label: "Active Memos",
    value: "24",
    trend: "+3 this week",
    icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
    tone: "navy",
  },
  {
    label: "Pending Approvals",
    value: "08",
    trend: "2 urgent",
    icon: "M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z",
    tone: "warning",
  },
  {
    label: "ECL Total (Stage 3)",
    value: "KD 1.4M",
    trend: "Impaired facilities",
    icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
    tone: "navy",
  },
  {
    label: "Compliance Flags",
    value: "03",
    trend: "1 shariah · 1 citation · 1 policy",
    icon: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z",
    tone: "warning",
  },
];

const stageBadge: Record<WorkflowStage, string> = {
  Draft: "badge-gray",
  "Risk Review": "badge-blue",
  "Credit Committee": "badge-green",
  "Shariah Board": "badge-amber",
  "Final Approval": "badge-navy",
};

const slaBadge: Record<SlaStatus, string> = {
  "On Track": "badge-green",
  "At Risk": "badge-amber",
  Overdue: "badge-red",
};

const workflowSteps = [
  { label: "Draft", state: "done" },
  { label: "Risk", state: "current" },
  { label: "Comm.", state: "pending" },
  { label: "Shariah", state: "pending" },
] as const;

const stageColors = ["#0F2A4A", "#64748B", "#F59E0B"];

function useCountdown(initialSeconds: number) {
  const [seconds, setSeconds] = useState(initialSeconds);
  useEffect(() => {
    const t = window.setInterval(() => {
      setSeconds((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => window.clearInterval(t);
  }, []);
  const hh = String(Math.floor(seconds / 3600)).padStart(2, "0");
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [memos, setMemos] = useState<MemoListItem[]>([]);
  const [eclData, setEclData] = useState<ECLResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [memosRes, eclRes] = await Promise.all([
          getMemos(),
          computeECL().catch(() => null),
        ]);
        setMemos(memosRes.memos);
        setEclData(eclRes);
        if (memosRes.memos.length > 0) {
          setSelectedId(memosRes.memos[0].id);
        }
      } catch (err) {
        push("Failed to load dashboard data", "error");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const selected = memos.find((m) => m.id === selectedId) ?? memos[0];

  const filtered = useMemo(() => {
    if (!search) return memos;
    const q = search.toLowerCase();
    return memos.filter(
      (m) =>
        m.id.toLowerCase().includes(q) ||
        m.client_name.toLowerCase().includes(q) ||
        m.facility_type.toLowerCase().includes(q) ||
        m.workflow_stage.toLowerCase().includes(q),
    );
  }, [search, memos]);

  const eclPie = eclData
    ? [
        { name: "Stage 1", label: "Low Risk", value: eclData.stage1_ecl },
        { name: "Stage 2", label: "Inc. Risk", value: eclData.stage2_ecl },
        { name: "Stage 3", label: "Impaired", value: eclData.stage3_ecl },
      ]
    : [];

  return (
    <div>
      {/* ── Header ─────────────────────────────────────── */}
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-frost-navy">Credit Dashboard</h1>
          <p className="mt-1 text-sm text-frost-slate">
            Memo pipeline, approvals, and portfolio intelligence — Q2 FY2026.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-outline" title="Reporting period">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
            </svg>
            Q2 FY2026
          </button>
          <button onClick={() => navigate("/generate")} className="btn-navy">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Generate New Memo
          </button>
        </div>
      </div>

      {/* ── KPI cards ──────────────────────────────────── */}
      <div className="mb-7 grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="card flex items-center gap-5 p-6">
            <div
              className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${
                kpi.tone === "warning" ? "bg-amber-50 text-status-warning" : "bg-frost-light text-frost-navy"
              }`}
            >
              <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.7} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d={kpi.icon} />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-bold uppercase tracking-wider text-frost-steel">
                {kpi.label}
              </p>
              <p className={`mt-1 font-display text-3xl font-bold ${kpi.tone === "warning" ? "text-status-warning" : "text-frost-deep"}`}>
                {kpi.value}
              </p>
              <p className="mt-0.5 truncate text-xs text-frost-slate">{kpi.trend}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ── Split view: pipeline (left) + panels (right) ── */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* LEFT — Memo Pipeline */}
        <div className="xl:col-span-2">
          <div className="card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-frost-mist px-6 py-4">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-bold text-frost-deep">Memo Pipeline</h2>
                <span className="badge-gray">Queue</span>
              </div>
              <div className="relative">
                <svg
                  className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-frost-steel"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter by ID, client, facility, stage…"
                  className="field !w-72 !py-2 pl-10 text-xs"
                  aria-label="Filter memos"
                />
              </div>
            </div>

            {loading ? (
              <SkeletonTable rows={5} cols={6} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead>
                    <tr className="table-head">
                      <th className="px-6 py-3">Memo ID</th>
                      <th className="px-4 py-3">Client</th>
                      <th className="px-4 py-3">Facility Type</th>
                      <th className="px-4 py-3">Stage</th>
                      <th className="px-4 py-3">SLA Status</th>
                      <th className="px-6 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((m) => (
                      <tr
                        key={m.id}
                        onClick={() => setSelectedId(m.id)}
                        className={`table-row cursor-pointer ${m.id === selected?.id ? "bg-blue-50/40" : ""}`}
                      >
                        <td className="px-6 py-4 font-mono text-xs font-semibold text-frost-navy">{m.id}</td>
                        <td className="px-4 py-4">
                          <p className="font-semibold text-frost-deep">{m.client_name}</p>
                          <p className="text-xs text-frost-steel">{m.client_id}</p>
                        </td>
                        <td className="px-4 py-4 text-frost-slate">{m.facility_type}</td>
                        <td className="px-4 py-4">
                          <span className={stageBadge[m.workflow_stage as WorkflowStage] || "badge-gray"}>● {m.workflow_stage}</span>
                        </td>
                        <td className="px-4 py-4">
                          <span className={slaBadge[m.sla_status || "On Track"]}>{m.sla_status || "On Track"}</span>
                          <p className="mt-1 text-xs text-frost-steel">
                            {m.sla_hours_remaining !== null
                              ? `${Math.round(m.sla_hours_remaining)}h remaining`
                              : "—"}
                          </p>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/review/${m.id}`);
                              }}
                              className="rounded-lg p-2 text-frost-slate transition hover:bg-frost-light hover:text-frost-navy"
                              title="View memo"
                            >
                              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedId(m.id);
                                push(`${m.id} escalation triggered.`, "info");
                              }}
                              className="rounded-lg p-2 text-frost-slate transition hover:bg-amber-50 hover:text-status-warning"
                              title="Escalate"
                            >
                              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex items-center justify-between border-t border-frost-mist px-6 py-3.5">
              <p className="text-xs text-frost-steel">
                Showing {filtered.length} of {memos.length} memos
              </p>
              <button
                onClick={() => push("Full pipeline view is available in the Reporting Center.", "info")}
                className="text-sm font-semibold text-frost-navy transition hover:text-gold"
              >
                View All Pipeline →
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT — Workflow / ECL / Alerts */}
        <div className="space-y-6">
          {/* Approval Workflow */}
          <div className="card p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-frost-deep">Approval Workflow</h2>
              {selected && selected.deal_value > 2_000_000 && (
                <span className="badge-amber">HIGH VALUE</span>
              )}
            </div>

            {selected && (
              <div className="panel-navy mt-4 px-5 py-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/50">Selected Memo</p>
                <p className="mt-1 text-sm font-semibold text-white">
                  {selected.id}: {selected.client_name}
                </p>
              </div>
            )}

            {/* 5-stage progress */}
            <div className="mt-5 flex items-center">
              {workflowSteps.map((s, i) => (
                <div key={s.label} className="flex flex-1 items-center last:flex-none">
                  <div className="flex flex-col items-center gap-1.5">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                        s.state === "done"
                          ? "bg-status-success text-white"
                          : s.state === "current"
                            ? "bg-frost-navy text-white ring-4 ring-frost-navy/15"
                            : "border-2 border-frost-mist bg-white text-frost-steel"
                      }`}
                    >
                      {s.state === "done" ? "✓" : i + 1}
                    </div>
                    <span className="text-[10px] font-semibold text-frost-slate">{s.label}</span>
                  </div>
                  {i < workflowSteps.length - 1 && (
                    <div
                      className={`mx-1 h-0.5 flex-1 rounded ${
                        s.state === "done" ? "bg-status-success" : "bg-frost-mist"
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>

            {selected && (
              <div className="mt-5 border-t border-frost-mist pt-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-frost-steel">Created By</p>
                    <p className="mt-1 text-sm font-semibold text-frost-deep">{selected.created_by}</p>
                    <p className="mt-0.5 text-xs text-frost-slate">{selected.facility_type}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-frost-steel">SLA Status</p>
                    <p className="mt-1 text-sm font-semibold text-frost-deep">
                      {selected.sla_status || "On Track"}
                    </p>
                    {selected.sla_hours_remaining !== null && !isNaN(selected.sla_hours_remaining) && (
                      <p className="mt-0.5 text-xs text-frost-slate">
                        {Math.round(selected.sla_hours_remaining)}h remaining
                      </p>
                    )}
                    {(selected.sla_hours_remaining === null || isNaN(selected.sla_hours_remaining)) && (
                      <p className="mt-0.5 text-xs text-frost-slate">—</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ECL Breakdown */}
          <div className="card p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-frost-deep">ECL Breakdown</h2>
              <span className="badge-gray">Validation Mode</span>
            </div>
            <p className="mt-1 text-xs text-frost-slate">Portfolio provision coverage by stage</p>

            <div className="mt-4 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={eclPie}
                    cx="50%"
                    cy="50%"
                    innerRadius={48}
                    outerRadius={68}
                    dataKey="value"
                    stroke="none"
                  >
                    {eclPie.map((_, i) => (
                      <Cell key={i} fill={stageColors[i]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => formatKD(v)}
                    contentStyle={{
                      borderRadius: 12,
                      border: "1px solid #E2E8F0",
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-2 space-y-1.5">
              {eclPie.map((s, i) => (
                <div key={s.name} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 text-frost-slate">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: stageColors[i] }} />
                    {s.name} ({s.label})
                  </span>
                  <span className="font-semibold text-frost-deep">{formatKD(s.value)}</span>
                </div>
              ))}
            </div>

            {eclData && (
              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-frost-mist pt-4">
                <div className="rounded-xl bg-frost-light px-4 py-3">
                  <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-frost-steel">Total ECL</p>
                  <p className="mt-1 font-display text-lg font-bold text-frost-navy">
                    {formatKD(eclData.total_ecl)}
                  </p>
                </div>
                <div className="rounded-xl bg-gold/10 px-4 py-3">
                  <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-frost-steel">Facilities</p>
                  <p className="mt-1 font-display text-lg font-bold text-frost-navy">
                    {eclData.stage_breakdown.reduce((s, b) => s + b.facility_count, 0)}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Compliance Alerts */}
          <div className="card p-6">
            <div className="flex items-center gap-2.5">
              <span className="h-2 w-2 rounded-full bg-status-danger" />
              <h2 className="text-base font-bold text-frost-deep">Compliance Alerts</h2>
            </div>
            <ul className="mt-4 space-y-4">
              {memos
                .filter((m) => m.shariah_flag_count > 0 || m.citation_flag_count > 0)
                .slice(0, 3)
                .map((m) => (
                  <li key={m.id} className="border-b border-frost-mist/60 pb-4 last:border-0 last:pb-0">
                    <div className="flex items-center justify-between">
                      <span className={m.shariah_flag_count > 0 ? "badge-red" : "badge-blue"}>
                        {m.shariah_flag_count > 0 ? "SHARIAH FLAG" : "CITATION ISSUE"}
                      </span>
                      <span className="text-[10px] text-frost-steel">{m.id}</span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-frost-slate">
                      {m.client_name} — {m.shariah_flag_count} shariah flag(s), {m.citation_flag_count} citation(s)
                    </p>
                    <button
                      onClick={() => navigate(`/review/${m.id}`)}
                      className="mt-1.5 text-sm font-semibold text-frost-navy transition hover:text-gold"
                    >
                      Review Now →
                    </button>
                  </li>
                ))}
              {memos.filter((m) => m.shariah_flag_count > 0 || m.citation_flag_count > 0).length === 0 && (
                <li className="text-sm text-frost-steel">No compliance alerts</li>
              )}
            </ul>
          </div>
        </div>
      </div>

      {/* ── Quick actions ───────────────────────────────── */}
      <div className="mt-7 grid grid-cols-1 gap-5 sm:grid-cols-3">
        <button
          onClick={() => push("Approval workspace opened for selected section.", "success")}
          className="btn-success w-full"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Approve Section
        </button>
        <button
          onClick={() => selected && push(`${selected.id} escalation triggered.`, "info")}
          className="btn-danger w-full"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
          </svg>
          Escalate
        </button>
        <button
          onClick={() => push("Memo report exported to PDF.", "success")}
          className="btn-outline w-full"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m.75 12l3 3m0 0l3-3m-3 3v-6m-1.5-9H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          Export Memo Report
        </button>
      </div>
    </div>
  );
}
