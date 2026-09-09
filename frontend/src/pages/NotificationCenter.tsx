import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/Toast";
import { getNotifications, markNotificationRead } from "../services/api";
import type { NotificationItem } from "../types/api";

const eventBadge: Record<string, string> = {
  memo_generated: "badge-blue",
  section_requires_review: "badge-amber",
  approval_stage_changed: "badge-green",
  finalization_ready: "badge-navy",
  sla_breach: "badge-red",
};

export default function NotificationCenter() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  useEffect(() => {
    fetchNotifications();
  }, []);

  async function fetchNotifications() {
    try {
      const res = await getNotifications();
      setNotifications(res.notifications);
      setUnreadCount(res.unread_count);
    } catch (err) {
      push("Failed to load notifications", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkRead(id: string) {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, status: "read" } : n)),
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
      push("Notification marked as read", "success");
    } catch {
      push("Failed to mark notification as read", "error");
    }
  }

  async function handleMarkAllRead() {
    try {
      await Promise.all(
        notifications.filter((n) => n.status !== "read").map((n) => markNotificationRead(n.id)),
      );
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, status: n.status === "read" ? n.status : "read" })),
      );
      setUnreadCount(0);
      push("All notifications marked as read", "success");
    } catch {
      push("Failed to mark all as read", "error");
    }
  }

  const filtered = filter === "unread" ? notifications.filter((n) => n.status !== "read") : notifications;

  return (
    <div>
      {/* ── Header ─────────────────────────────────────── */}
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-frost-navy">Notification Center</h1>
          <p className="mt-1 text-sm text-frost-slate">
            Stay updated on memo activity, approvals, and compliance alerts.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-xl bg-frost-light p-1">
            {(["all", "unread"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-lg px-4 py-2 text-xs font-bold tracking-wide transition ${
                  filter === f ? "bg-frost-navy text-white shadow-card" : "text-frost-slate hover:text-frost-navy"
                }`}
              >
                {f === "all" ? "All" : `Unread (${unreadCount})`}
              </button>
            ))}
          </div>
          {unreadCount > 0 && (
            <button onClick={handleMarkAllRead} className="btn-outline">
              Mark All Read
            </button>
          )}
        </div>
      </div>

      {/* ── Notifications list ─────────────────────────── */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="px-6 py-12 text-center text-sm text-frost-steel">Loading notifications...</div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-frost-steel">
            {filter === "unread" ? "No unread notifications" : "No notifications yet"}
          </div>
        ) : (
          <ul className="divide-y divide-frost-mist">
            {filtered.map((n) => {
              const isRead = n.status === "read";
              return (
            <li
              key={n.id}
              className={`flex items-start gap-4 px-6 py-5 transition hover:bg-frost-light/50 ${
                !isRead ? "bg-blue-50/30" : ""
              }`}
            >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-frost-light">
                  <svg
                    className="h-5 w-5 text-frost-navy"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.8}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
                    />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className={eventBadge[n.event_type] || "badge-gray"}>
                          {n.event_type.replace(/_/g, " ").toUpperCase()}
                        </span>
                        <span className="text-xs text-frost-steel">{n.channel}</span>
                      </div>
                      <p className="mt-2 text-sm font-semibold text-frost-deep">{n.subject}</p>
                      <p className="mt-1 text-sm leading-relaxed text-frost-slate">{n.body}</p>
                      {n.client_name && (
                        <p className="mt-1 text-xs text-frost-slate">Client: {n.client_name}</p>
                      )}
                      <div className="mt-2 flex items-center gap-3 text-xs text-frost-steel">
                        <span>{new Date(n.sent_at || n.timestamp).toLocaleString()}</span>
                        {!isRead && (
                          <button
                            onClick={() => handleMarkRead(n.id)}
                            className="font-semibold text-frost-navy underline decoration-gold decoration-2 underline-offset-4 transition hover:text-gold"
                          >
                            Mark as read
                          </button>
                        )}
                        {n.memo_id && (
                          <button
                            onClick={() => navigate(`/review/${n.memo_id}`)}
                            className="font-semibold text-frost-navy underline decoration-gold decoration-2 underline-offset-4 transition hover:text-gold"
                          >
                            View memo →
                          </button>
                        )}
                      </div>
                    </div>
                    {!isRead && (
                      <div className="h-2.5 w-2.5 shrink-0 rounded-full bg-status-warning" />
                    )}
                  </div>
                </div>
              </li>
                );
              })}
          </ul>
        )}

        {filtered.length > 0 && (
          <div className="border-t border-frost-mist px-6 py-3.5">
            <p className="text-xs text-frost-steel">
              Showing {filtered.length} notification{filtered.length !== 1 ? "s" : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
