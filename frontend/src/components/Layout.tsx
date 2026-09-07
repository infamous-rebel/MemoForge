import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { getNotifications } from "../services/api";

const tabs = [
  { to: "/", label: "Memos" },
  { to: "/ecl", label: "Compliance" },
  { to: "/reports", label: "Reports" },
  { to: "/admin", label: "Admin" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const role = localStorage.getItem("role") || "RM";
  const userId = localStorage.getItem("user_id") || "analyst";
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    async function fetchUnread() {
      try {
        const res = await getNotifications();
        setUnreadCount(res.unread_count);
      } catch {
        // Silently fail
      }
    }
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("user_id");
    navigate("/login");
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-frost-surface">
      {/* ── Top bar ─────────────────────────────────────────── */}
      <header className="z-20 border-b border-frost-mist bg-white">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-6 px-6 py-3.5">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-frost-navy shadow-card">
              <span className="font-display text-lg font-bold text-gold">M</span>
            </div>
            <div className="leading-tight">
              <p className="font-display text-lg font-bold text-frost-navy">MemoForge</p>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-frost-steel">
                Credit Lifecycle · Warba Bank
              </p>
            </div>
          </div>

          {/* Tabs */}
          <nav
            className="hidden items-center gap-1 rounded-xl bg-frost-light p-1 md:flex"
            aria-label="Primary"
          >
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-5 py-2 text-sm font-semibold transition ${
                    isActive
                      ? "bg-frost-navy text-white shadow-card"
                      : "text-frost-slate hover:text-frost-navy"
                  }`
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>

          {/* User panel */}
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full border border-frost-mist bg-white py-1.5 pl-3 pr-4 sm:flex">
              <span className="h-2 w-2 rounded-full bg-status-success" aria-label="Online" />
              <span className="text-xs font-bold text-frost-navy">{role} — Risk Mode</span>
            </div>
            <button
              className="text-frost-slate transition hover:text-status-success"
              title="Security posture: protected"
              aria-label="Security status"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.7} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </button>
            <button
              onClick={() => navigate("/notifications")}
              className="relative text-frost-slate transition hover:text-frost-navy"
              title="Notifications"
              aria-label="Notifications"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.7} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
              {unreadCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-status-danger text-[9px] font-bold text-white">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={handleLogout}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-frost-navy font-display text-sm font-bold text-gold transition hover:bg-frost-deep"
              title={`${userId} — Logout`}
            >
              {userId.charAt(0).toUpperCase()}
            </button>
          </div>
        </div>

        {/* Mobile tabs */}
        <nav className="flex gap-1 overflow-x-auto border-t border-frost-mist px-4 py-2 md:hidden" aria-label="Primary mobile">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.to === "/"}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-4 py-1.5 text-xs font-semibold ${
                  isActive ? "bg-frost-navy text-white" : "bg-frost-light text-frost-slate"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {/* ── Main ────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1440px] animate-fadeIn px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
