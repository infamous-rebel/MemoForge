import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useToast } from "../components/Toast";

const howItWorks = [
  {
    step: "01",
    title: "Retrieve",
    desc: "RAG pulls client data with ACL filtering — financials, collateral, and credit history flow in from your vault, never beyond it.",
    icon: "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z",
  },
  {
    step: "02",
    title: "Synthesize",
    desc: "Agents compute ratios, ECL, and draft narrative with citations. Every figure traces back to a source document chunk.",
    icon: "M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5",
  },
  {
    step: "03",
    title: "Approve",
    desc: "Human-in-the-loop with deterministic rules, Shariah Board review, and a full hash-chained audit trail.",
    icon: "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

const features = [
  {
    title: "Provider-Agnostic LLM",
    desc: "Anthropic, OpenAI, Azure, Bedrock, or Ollama — swap models without touching agent code.",
    icon: "M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z",
  },
  {
    title: "Shariah Compliance Engine",
    desc: "Facility-type aware terminology validation for Murabaha, Ijara, Musharakah, Sukuk, and Tawarruq.",
    icon: "M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z",
  },
  {
    title: "CBK / IFRS 9 ECL Engine",
    desc: "Three-stage model with 1% PD floor, 30+ DPD triggers, and full per-facility auditability.",
    icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
  },
  {
    title: "Five-Stage Approval Workflow",
    desc: "Draft → Risk → Credit Committee → Shariah Board → Final, with SLA tracking and escalation.",
    icon: "M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12",
  },
  {
    title: "Hash-Chained Audit Log",
    desc: "SHA-256 chained events make the trail tamper-evident — every decision is provable.",
    icon: "M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z",
  },
  {
    title: "Integration Layer",
    desc: "Typed connectors for CRM, Core Banking, and Market Data — mock today, live in your VPC tomorrow.",
    icon: "M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244",
  },
];

const comparisonRows = [
  { label: "Shariah-compliance", memoforge: true, traditional: false, western: false },
  { label: "CBK alignment", memoforge: true, traditional: true, western: false },
  { label: "Source-cited generation", memoforge: true, traditional: false, western: true },
  { label: "Human-in-the-loop", memoforge: true, traditional: true, western: false },
  { label: "Tamper-evident audit trail", memoforge: true, traditional: false, western: false },
  { label: "Deployment sovereignty", memoforge: true, traditional: true, western: false },
];

function CheckIcon() {
  return (
    <span className="mx-auto flex h-7 w-7 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
      <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
    </span>
  );
}

function XIcon() {
  return (
    <span className="mx-auto flex h-7 w-7 items-center justify-center rounded-full bg-frost-light text-frost-steel">
      <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </span>
  );
}

const securityPoints = [
  {
    title: "ISO 27001 Aligned",
    desc: "Security controls mapped to ISO 27001 domains, with SOC 2 readiness tracking.",
    icon: "M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z",
  },
  {
    title: "Data Residency",
    desc: "No data leaves the bank's VPC. LLM endpoints are private deployments or approved regions.",
    icon: "M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418",
  },
  {
    title: "Zero Write-Back",
    desc: "Read-only integration with core systems. MemoForge never mutates banking records.",
    icon: "M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636",
  },
  {
    title: "Role-Based Access Control",
    desc: "Five roles — RM, Risk, Credit Committee, Shariah Board, Admin — enforced at API and data layers.",
    icon: "M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z",
  },
];

export default function Landing() {
  const { push } = useToast();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [bank, setBank] = useState("");

  const handlePilot = (e: FormEvent) => {
    e.preventDefault();
    if (!name || !email || !bank) return;
    push(
      `Thank you, ${name}. Our team will contact you at ${email} to schedule the ${bank} pilot.`,
      "success",
    );
    setName("");
    setEmail("");
    setBank("");
  };

  return (
    <div className="min-h-screen bg-white">
      {/* ── Nav ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-frost-mist/60 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-frost-navy">
              <span className="font-display text-lg font-bold text-gold">M</span>
            </div>
            <div className="leading-tight">
              <p className="font-display text-lg font-bold text-frost-navy">MemoForge</p>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-frost-steel">
                Islamic Banking Edition
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="btn-ghost hidden sm:inline-flex">
              Sign In
            </Link>
            <a href="#pilot" className="btn-navy">
              Request a Pilot
            </a>
          </div>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-frost-navy">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 30%, #C9A227 0%, transparent 40%), radial-gradient(circle at 80% 70%, #64748B 0%, transparent 45%)",
          }}
        />
        <div className="relative mx-auto max-w-7xl px-6 py-24 lg:py-32">
          <div className="max-w-3xl">
            <span className="badge border border-white/15 bg-white/10 text-white/90">
              <span className="h-1.5 w-1.5 rounded-full bg-gold" />
              Built for Warba Bank · Kuwait
            </span>
            <h1 className="mt-6 font-display text-4xl font-bold leading-tight text-white sm:text-5xl lg:text-6xl">
              AI-Powered Client Documentation Engine for{" "}
              <span className="text-gold">Islamic Banks</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/75">
              Generate Shariah-compliant credit memos in under an hour, not 1–3 days.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <a href="#pilot" className="btn-gold px-8 py-3.5 text-base">
                Request a Pilot
              </a>
              <a
                href="#how-it-works"
                className="inline-flex items-center gap-2 rounded-xl border border-white/25 px-8 py-3.5 text-base font-semibold text-white transition hover:bg-white/10"
              >
                Learn More
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                </svg>
              </a>
            </div>
          </div>

          {/* Stat strip */}
          <div className="mt-16 grid max-w-3xl grid-cols-3 divide-x divide-white/10 rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
            {[
              { v: "<1 hr", l: "Memo turnaround" },
              { v: "5", l: "Facility types governed" },
              { v: "100%", l: "Cited generation" },
            ].map((s) => (
              <div key={s.l} className="px-6 py-5 text-center">
                <p className="font-display text-2xl font-bold text-gold sm:text-3xl">{s.v}</p>
                <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-white/60">{s.l}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Problem ─────────────────────────────────────── */}
      <section className="bg-frost-surface py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <p className="tag-label">The Problem</p>
              <blockquote className="mt-4 border-l-4 border-gold pl-6">
                <p className="font-display text-2xl font-medium italic leading-relaxed text-frost-deep sm:text-3xl">
                  "Relationship Managers spend 70–75% of their time on documentation, not client
                  dialogue."
                </p>
              </blockquote>
              <p className="mt-6 max-w-lg leading-relaxed text-frost-slate">
                Credit memos take days to assemble by hand: retrieving statements, computing ratios,
                aligning Shariah terminology, and chasing approvals. The cost is measured in missed
                conversations and delayed decisions.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-5">
              <div className="card p-8">
                <p className="tag-label">Traditional Process</p>
                <p className="mt-3 font-display text-4xl font-bold text-status-danger">4–8 hrs</p>
                <p className="mt-2 text-sm text-frost-slate">
                  Manual assembly, copy-paste ratios, untracked review cycles.
                </p>
              </div>
              <div className="card mt-8 border-2 border-status-success/30 p-8">
                <p className="tag-label text-status-success">With MemoForge</p>
                <p className="mt-3 font-display text-4xl font-bold text-status-success">&lt;1 hr</p>
                <p className="mt-2 text-sm text-frost-slate">
                  Pipeline-generated, source-cited, compliance-checked, approval-routed.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How It Works ────────────────────────────────── */}
      <section id="how-it-works" className="bg-white py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <p className="tag-label">How It Works</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-frost-navy sm:text-4xl">
              Retrieve. Synthesize. Approve.
            </h2>
            <p className="mt-4 leading-relaxed text-frost-slate">
              A deterministic pipeline with humans where they matter — not a black box.
            </p>
          </div>

          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {howItWorks.map((s, i) => (
              <div key={s.title} className="relative">
                {i < 2 && (
                  <div className="absolute left-full top-10 hidden h-px w-8 -translate-x-4 bg-frost-mist md:block" />
                )}
                <div className="card h-full p-8">
                  <div className="flex items-center justify-between">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-frost-navy text-white">
                      <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d={s.icon} />
                      </svg>
                    </div>
                    <span className="font-display text-4xl font-bold text-frost-mist">{s.step}</span>
                  </div>
                  <h3 className="mt-6 text-xl font-bold text-frost-navy">{s.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-frost-slate">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────── */}
      <section className="bg-frost-surface py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <p className="tag-label">Key Features</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-frost-navy sm:text-4xl">
              Enterprise-grade, end to end
            </h2>
          </div>
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <div key={f.title} className="card p-8 transition hover:shadow-panel">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gold/15 text-gold">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d={f.icon} />
                  </svg>
                </div>
                <h3 className="mt-5 text-lg font-bold text-frost-navy">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-frost-slate">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Comparison ──────────────────────────────────── */}
      <section className="bg-white py-24">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <p className="tag-label">Why MemoForge</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-frost-navy sm:text-4xl">
              The only engine built for Islamic banking
            </h2>
          </div>

          <div className="card mt-14 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="table-head">
                  <th className="px-6 py-4 text-left">Capability</th>
                  <th className="px-6 py-4 text-center">
                    <span className="font-display text-base font-bold text-frost-navy">MemoForge</span>
                  </th>
                  <th className="px-6 py-4 text-center text-frost-slate">Traditional Tools</th>
                  <th className="px-6 py-4 text-center text-frost-slate">Western AI Platforms</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.label} className="table-row">
                    <td className="px-6 py-4 font-semibold text-frost-deep">{row.label}</td>
                    <td className="bg-emerald-50/40 px-6 py-4">
                      {row.memoforge ? <CheckIcon /> : <XIcon />}
                    </td>
                    <td className="px-6 py-4">{row.traditional ? <CheckIcon /> : <XIcon />}</td>
                    <td className="px-6 py-4">{row.western ? <CheckIcon /> : <XIcon />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Compliance & Security ───────────────────────── */}
      <section className="bg-frost-navy py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <p className="tag-label text-white/50">Compliance & Security</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-white sm:text-4xl">
              Sovereign by design
            </h2>
          </div>
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {securityPoints.map((p) => (
              <div key={p.title} className="rounded-2xl border border-white/10 bg-white/5 p-7 backdrop-blur">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gold/20 text-gold">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d={p.icon} />
                  </svg>
                </div>
                <h3 className="mt-5 text-base font-bold text-white">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/65">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────── */}
      <section id="pilot" className="bg-white py-24">
        <div className="mx-auto max-w-4xl px-6">
          <div className="card overflow-hidden">
            <div className="grid lg:grid-cols-5">
              <div className="panel-navy flex flex-col justify-center p-10 lg:col-span-2">
                <h2 className="font-display text-3xl font-bold">Request a Pilot</h2>
                <p className="mt-4 text-sm leading-relaxed text-white/70">
                  See MemoForge generate a live memo from your own portfolio structure — inside
                  your environment, under your governance.
                </p>
                <ul className="mt-8 space-y-3 text-sm text-white/80">
                  {["4-week guided pilot", "Your data, your VPC", "Shariah Board walkthrough included"].map((t) => (
                    <li key={t} className="flex items-center gap-3">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gold/20 text-xs font-bold text-gold">
                        ✓
                      </span>
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
              <form onSubmit={handlePilot} className="space-y-5 p-10 lg:col-span-3">
                <div>
                  <label htmlFor="pilot-name" className="field-label">Full Name</label>
                  <input
                    id="pilot-name"
                    className="field"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ahmad Al-Sabah"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="pilot-email" className="field-label">Work Email</label>
                  <input
                    id="pilot-email"
                    type="email"
                    className="field"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ahmad@yourbank.com"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="pilot-bank" className="field-label">Institution</label>
                  <input
                    id="pilot-bank"
                    className="field"
                    value={bank}
                    onChange={(e) => setBank(e.target.value)}
                    placeholder="Warba Bank"
                    required
                  />
                </div>
                <button type="submit" className="btn-navy w-full py-3.5">
                  Request a Pilot
                </button>
                <p className="text-center text-xs text-frost-steel">
                  Or contact us directly — pilots@memoforge.ai
                </p>
              </form>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="border-t border-frost-mist bg-frost-surface">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-6 py-10 sm:flex-row">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-frost-navy">
              <span className="font-display text-sm font-bold text-gold">M</span>
            </div>
            <p className="text-sm text-frost-slate">
              © {new Date().getFullYear()} MemoForge. 100% Shariah-compliant. CBK/IFRS 9 aligned.
            </p>
          </div>
          <div className="flex items-center gap-6 text-sm font-semibold text-frost-slate">
            <a href="#how-it-works" className="transition hover:text-frost-navy">Documentation</a>
            <a href="#pilot" className="transition hover:text-frost-navy">Contact</a>
            <Link to="/login" className="transition hover:text-frost-navy">Sign In</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
