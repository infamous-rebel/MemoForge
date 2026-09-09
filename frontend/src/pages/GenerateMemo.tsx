import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { generateMemo } from "../services/api";
import { useToast } from "../components/Toast";

const FACILITY_TYPES = ["Murabaha", "Ijara", "Musharakah", "Sukuk", "Tawarruq"];

const CLIENTS = [
  { id: "CORP-001", name: "Kuwait Tech Logix (KTL)", sector: "Digital Infrastructure" },
  { id: "CORP-002", name: "Gulf Al-Oula Ltd (GA)", sector: "Logistics" },
  { id: "CORP-003", name: "Beacon National (BN)", sector: "Trading" },
  { id: "CORP-004", name: "Amghara Industries (AI)", sector: "Manufacturing" },
  { id: "CORP-005", name: "Sharq Holdings (SH)", sector: "Real Estate" },
];

const PIPELINE_AGENTS = [
  { name: "Data Retrieval", detail: "RAG + connectors · ACL-filtered" },
  { name: "Data Validation", detail: "Confidence & freshness scoring" },
  { name: "Ratio Computation", detail: "DSCR · leverage · liquidity" },
  { name: "ECL Engine", detail: "CBK / IFRS 9 three-stage" },
  { name: "Risk Intelligence", detail: "Risk identification & severity" },
  { name: "Narrative Generation", detail: "Sections with citations" },
  { name: "Compliance Agent", detail: "Shariah + citation guardrails" },
  { name: "Approval Routing", detail: "Deterministic HITL rules" },
];

export default function GenerateMemo() {
  const navigate = useNavigate();
  const { push } = useToast();
  const role = localStorage.getItem("role") || "RM";

  const [step, setStep] = useState(1);
  const [client, setClient] = useState(CLIENTS[0]);
  const [facilityType, setFacilityType] = useState("Murabaha");
  const [dealValue, setDealValue] = useState(1_250_000);
  const [complianceMode, setComplianceMode] = useState(true);
  const [running, setRunning] = useState(false);
  const [agentProgress, setAgentProgress] = useState(0);

  // Animate pipeline agents in step 3
  useEffect(() => {
    if (step !== 3 || !running) return;
    if (agentProgress >= PIPELINE_AGENTS.length) return;
    const t = window.setTimeout(() => setAgentProgress((p) => p + 1), 650);
    return () => window.clearTimeout(t);
  }, [step, running, agentProgress]);

  // Pipeline completion → navigate to review
  useEffect(() => {
    if (step === 3 && running && agentProgress >= PIPELINE_AGENTS.length) {
      const t = window.setTimeout(async () => {
        try {
          const res = await generateMemo({
            client_id: client.id,
            client_name: client.name,
            facility_type: facilityType.toLowerCase(),
            deal_value: dealValue,
          });
          push("Memo generated — routed for review.", "success");
          navigate(`/review/${res.memo_id}`);
        } catch {
          push("Memo generation failed. Please try again.", "error");
          navigate("/dashboard");
        }
      }, 700);
      return () => window.clearTimeout(t);
    }
  }, [agentProgress, step, running, client, facilityType, dealValue, navigate, push]);

  // Only RM and Admin may generate memos (guard after all hooks)
  if (role !== "RM" && role !== "Admin") {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-red-50">
            <svg className="h-8 w-8 text-status-danger" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <p className="mt-4 text-lg font-bold text-frost-navy">Access Restricted</p>
          <p className="mt-2 text-sm text-frost-slate">
            Only Relationship Managers and Admins can initiate memo generation.<br />
            Your role ({role}) is limited to review and approval.
          </p>
          <button onClick={() => navigate("/dashboard")} className="btn-navy mt-5">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const handleGenerate = (e: FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setAgentProgress(0);
    setStep(3);
    push("Live pipeline started for " + client.name, "info");
  };

  const stepMeta = [
    { n: 1, label: "Configuration", state: step === 1 ? "ACTIVE STEP" : step > 1 ? "COMPLETED" : "PENDING" },
    { n: 2, label: "Review & Confirm", state: step === 2 ? "ACTIVE STEP" : step > 2 ? "COMPLETED" : "PENDING" },
    { n: 3, label: "Live Pipeline", state: step === 3 ? "GENERATION" : "PENDING" },
  ];

  return (
    <div className="min-h-[calc(100vh-57px)] lg:flex">
      {/* ── Left sidebar ─────────────────────────────────── */}
      <aside className="relative overflow-hidden bg-frost-navy px-8 py-10 lg:w-80 lg:shrink-0">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: "radial-gradient(circle at 70% 20%, #C9A227 0%, transparent 45%)" }}
        />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
              <span className="font-display text-lg font-bold text-gold">M</span>
            </div>
            <div className="leading-tight">
              <p className="font-display text-lg font-bold text-white">MemoForge</p>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-white/40">
                Credit Lifecycle
              </p>
            </div>
          </div>

          <nav className="mt-14 space-y-2" aria-label="Wizard steps">
            {stepMeta.map((s) => (
              <div key={s.n} className="flex items-start gap-4">
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                    s.state === "COMPLETED"
                      ? "bg-status-success text-white"
                      : s.state === "ACTIVE STEP" || s.state === "GENERATION"
                        ? "bg-gold text-frost-navy"
                        : "border border-white/20 text-white/40"
                  }`}
                >
                  {s.state === "COMPLETED" ? "✓" : s.n}
                </div>
                <div>
                  <p className={`text-sm font-semibold ${s.state === "PENDING" ? "text-white/40" : "text-white"}`}>
                    {s.label}
                  </p>
                  <p
                    className={`mt-0.5 text-[9px] font-bold uppercase tracking-[0.14em] ${
                      s.state === "ACTIVE STEP" || s.state === "GENERATION"
                        ? "text-gold"
                        : "text-white/30"
                    }`}
                  >
                    {s.state}
                  </p>
                </div>
              </div>
            ))}
          </nav>

          <p className="mt-14 text-[9px] font-bold uppercase tracking-[0.2em] text-white/30">
            Islamic Banking Edition
          </p>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────── */}
      <div className="flex-1 bg-gradient-to-br from-frost-surface to-white px-6 py-10 lg:px-14">
        <div className="mx-auto max-w-2xl">
          {/* Step 1 — Configuration */}
          {step === 1 && (
            <form
              className="animate-fadeIn"
              onSubmit={(e) => {
                e.preventDefault();
                setStep(2);
              }}
            >
              <h1 className="font-display text-3xl font-bold text-frost-navy">Generate Credit Memo</h1>
              <p className="mt-2 leading-relaxed text-frost-slate">
                Select a client and facility parameters to trigger the AI-orchestrated credit memo
                generation pipeline.
              </p>

              <div className="mt-10 space-y-7">
                <div>
                  <label htmlFor="client" className="field-label">Select Client</label>
                  <div className="relative">
                    <svg
                      className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-frost-navy"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.6}
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
                    </svg>
                    <select
                      id="client"
                      className="field !py-4 pl-12 pr-10"
                      value={client.id}
                      onChange={(e) => setClient(CLIENTS.find((c) => c.id === e.target.value) ?? CLIENTS[0])}
                    >
                      {CLIENTS.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <p className="mt-2 text-xs text-frost-steel">Sector: {client.sector}</p>
                </div>

                <div>
                  <label htmlFor="facility" className="field-label">Facility Type</label>
                  <div className="relative">
                    <svg
                      className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-frost-navy"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.6}
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                    <select
                      id="facility"
                      className="field !py-4 pl-12 pr-10"
                      value={facilityType}
                      onChange={(e) => setFacilityType(e.target.value)}
                    >
                      {FACILITY_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label htmlFor="deal-value" className="field-label">Deal Value (KD)</label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 rounded-md bg-frost-light px-2 py-0.5 text-[10px] font-bold text-frost-slate">
                      KD
                    </span>
                    <input
                      id="deal-value"
                      type="number"
                      className="field !py-4 pl-16 font-mono text-lg font-bold"
                      value={dealValue}
                      min={10_000}
                      step={50_000}
                      onChange={(e) => setDealValue(Math.max(0, Number(e.target.value)))}
                      required
                    />
                  </div>
                  <p className="mt-2 text-xs text-frost-steel">
                    Minimum KD 10,000. Deals above KD 5,000,000 always route to committee review.
                    The entered value will be used throughout the pipeline and final document.
                  </p>
                </div>

                <div>
                  <p className="field-label">Compliance Mode</p>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={complianceMode}
                    onClick={() => setComplianceMode((v) => !v)}
                    className="flex w-full items-center justify-between rounded-xl border border-frost-mist bg-white px-5 py-4 text-left shadow-sm transition hover:border-frost-navy/30"
                  >
                    <span className="flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z" />
                        </svg>
                      </span>
                      <span>
                        <span className="block text-sm font-bold text-frost-deep">Islamic Banking Standards</span>
                        <span className={`mt-0.5 block text-xs font-semibold ${complianceMode ? "text-status-success" : "text-frost-steel"}`}>
                          {complianceMode ? "Automatic Shariah Governance enabled" : "Shariah governance disabled"}
                        </span>
                      </span>
                    </span>
                    <span
                      className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                        complianceMode ? "bg-status-success" : "bg-frost-mist"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                          complianceMode ? "left-[22px]" : "left-0.5"
                        }`}
                      />
                    </span>
                  </button>
                </div>
              </div>

              <div className="mt-10 flex items-center justify-between">
                <button type="button" onClick={() => navigate("/dashboard")} className="btn-ghost text-frost-steel">
                  Cancel Process
                </button>
                <button type="submit" className="btn-navy px-6">
                  Next: Review Parameters
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              </div>
            </form>
          )}

          {/* Step 2 — Review & Confirm */}
          {step === 2 && (
            <form className="animate-fadeIn" onSubmit={handleGenerate}>
              <h1 className="font-display text-3xl font-bold text-frost-navy">Review & Confirm</h1>
              <p className="mt-2 leading-relaxed text-frost-slate">
                Confirm the pipeline parameters. Generation runs the full agent chain: retrieval,
                validation, ratios, ECL, narrative, and compliance.
              </p>

              <dl className="card mt-10 divide-y divide-frost-mist/60">
                {[
                  ["Client", client.name],
                  ["Client ID", client.id],
                  ["Sector", client.sector],
                  ["Facility Type", facilityType],
                  ["Deal Value", `KD ${dealValue.toLocaleString()}`],
                  ["Compliance Mode", complianceMode ? "Islamic Banking Standards" : "Standard"],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between px-6 py-4">
                    <dt className="text-xs font-bold uppercase tracking-wider text-frost-steel">{k}</dt>
                    <dd className="text-sm font-semibold text-frost-deep">{v}</dd>
                  </div>
                ))}
              </dl>

              {dealValue > 5_000_000 && (
                <div className="mt-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
                  <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                  Deal value exceeds the KD 5M threshold — this memo will always route to
                  Credit Committee review.
                </div>
              )}

              <div className="mt-10 flex items-center justify-between">
                <button type="button" onClick={() => setStep(1)} className="btn-ghost text-frost-steel">
                  ← Back to Configuration
                </button>
                <button type="submit" className="btn-gold px-6">
                  Trigger Live Pipeline
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </button>
              </div>
            </form>
          )}

          {/* Step 3 — Live Pipeline */}
          {step === 3 && (
            <div className="animate-fadeIn">
              <h1 className="font-display text-3xl font-bold text-frost-navy">Live Pipeline</h1>
              <p className="mt-2 leading-relaxed text-frost-slate">
                Agent chain executing for {client.name} — {facilityType} facility,
                KD {dealValue.toLocaleString()}.
              </p>

              <div className="card mt-10 divide-y divide-frost-mist/60">
                {PIPELINE_AGENTS.map((a, i) => {
                  const done = i < agentProgress;
                  const active = i === agentProgress;
                  return (
                    <div key={a.name} className="flex items-center gap-4 px-6 py-4">
                      <div
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                          done
                            ? "bg-status-success text-white"
                            : active
                              ? "bg-frost-navy text-white ring-4 ring-frost-navy/15"
                              : "bg-frost-light text-frost-steel"
                        }`}
                      >
                        {done ? "✓" : active ? (
                          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                        ) : (
                          i + 1
                        )}
                      </div>
                      <div className="flex-1">
                        <p className={`text-sm font-semibold ${done || active ? "text-frost-deep" : "text-frost-steel"}`}>
                          {a.name}
                        </p>
                        <p className="text-xs text-frost-steel">{a.detail}</p>
                      </div>
                      {done && <span className="badge-green">Complete</span>}
                      {active && <span className="badge-blue">Running</span>}
                    </div>
                  );
                })}
              </div>

              {/* Progress bar */}
              <div className="mt-6">
                <div className="flex items-center justify-between text-xs font-semibold text-frost-steel">
                  <span>Pipeline progress</span>
                  <span>
                    {Math.round((agentProgress / PIPELINE_AGENTS.length) * 100)}%
                  </span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-frost-mist">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-frost-navy to-gold transition-all duration-500"
                    style={{ width: `${(agentProgress / PIPELINE_AGENTS.length) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          <p className="mt-12 text-center text-[10px] font-bold uppercase tracking-[0.2em] text-frost-steel/60">
            MemoForge Production-Grade Pipeline — v2.4.0
          </p>
        </div>
      </div>
    </div>
  );
}
