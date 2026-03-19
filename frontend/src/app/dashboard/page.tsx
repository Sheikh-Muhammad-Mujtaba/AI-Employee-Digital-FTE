"use client";

import { useEffect, useState } from "react";
import { fetchDashboard, type DashboardData } from "@/lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div>
        <h1 className="page-title">Dashboard</h1>
        <div className="alert-banner">⚠️ {error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Loading…</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="page-title">Dashboard Overview</h1>
      <p className="page-subtitle">
        {data.tier} Tier — v{data.version} — Last updated: {data.last_updated}
      </p>

      {/* Alerts */}
      {data.alerts.map((a, i) => (
        <div key={i} className="alert-banner">
          {a}
        </div>
      ))}

      {/* Stat Cards */}
      <div className="stat-grid">
        <div className="glass-card stat-card animate-in">
          <div className="stat-card__label">Pending Inbox</div>
          <div className="stat-card__value" style={{ color: "var(--accent-cyan)" }}>
            {data.inbox_summary.pending_inbox}
          </div>
        </div>
        <div className="glass-card stat-card animate-in animate-in-delay-1">
          <div className="stat-card__label">Needs Action</div>
          <div className="stat-card__value" style={{ color: "var(--accent-amber)" }}>
            {data.inbox_summary.needs_action}
          </div>
        </div>
        <div className="glass-card stat-card animate-in animate-in-delay-2">
          <div className="stat-card__label">Pending Approval</div>
          <div className="stat-card__value" style={{ color: "var(--accent-purple)" }}>
            {data.inbox_summary.pending_approval}
          </div>
        </div>
        <div className="glass-card stat-card animate-in animate-in-delay-3">
          <div className="stat-card__label">Completed Today</div>
          <div className="stat-card__value" style={{ color: "var(--accent-emerald)" }}>
            {data.inbox_summary.completed_today}
          </div>
        </div>
        <div className="glass-card stat-card animate-in animate-in-delay-4">
          <div className="stat-card__label">Active Plans</div>
          <div className="stat-card__value" style={{ color: "var(--accent-blue)" }}>
            {data.inbox_summary.active_plans}
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="section-title" style={{ marginTop: 16 }}>System Status</div>
      <div className="glass-card" style={{ padding: 0, overflow: "hidden", marginBottom: 32 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Component</th>
              <th>Status</th>
              <th>Last Check</th>
            </tr>
          </thead>
          <tbody>
            {data.system_status.map((c, i) => (
              <tr key={i}>
                <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{c.name}</td>
                <td>
                  <span
                    className={`badge ${
                      c.status.includes("OK")
                        ? "badge--ok"
                        : c.status.includes("Idle")
                        ? "badge--idle"
                        : "badge--warn"
                    }`}
                  >
                    <span
                      className={`pulse-dot ${
                        c.status.includes("OK")
                          ? "pulse-dot--green"
                          : c.status.includes("Idle")
                          ? "pulse-dot--gray"
                          : "pulse-dot--yellow"
                      }`}
                    />
                    {c.status}
                  </span>
                </td>
                <td>{c.last_check}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Social Queue */}
      <div className="section-title">Social Queue</div>
      <div className="glass-card" style={{ padding: 0, overflow: "hidden", marginBottom: 32 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Queued</th>
              <th>Posted</th>
              <th>Last Post</th>
            </tr>
          </thead>
          <tbody>
            {data.social_queue.map((s, i) => (
              <tr key={i}>
                <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{s.platform}</td>
                <td>
                  <span
                    className={`badge ${s.queued > 0 ? "badge--warn" : "badge--ok"}`}
                  >
                    {s.queued}
                  </span>
                </td>
                <td>{s.posted}</td>
                <td>{s.last_post}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Accounting */}
      <div className="section-title">Accounting (Odoo)</div>
      <div className="glass-card" style={{ padding: 0, overflow: "hidden", marginBottom: 32 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
              <th>Last Sync</th>
            </tr>
          </thead>
          <tbody>
            {data.accounting.map((a, i) => (
              <tr key={i}>
                <td>{a.metric}</td>
                <td style={{ fontWeight: 600 }}>{a.value}</td>
                <td>{a.last_sync}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent Activity */}
      <div className="section-title">Recent Activity</div>
      <div className="glass-card" style={{ padding: 0, overflow: "hidden", marginBottom: 32 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_activity.slice(0, 10).map((ev, i) => (
              <tr key={i}>
                <td style={{ whiteSpace: "nowrap", fontSize: "0.8rem" }}>{ev.time}</td>
                <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{ev.event}</td>
                <td style={{ fontSize: "0.82rem", maxWidth: 500 }}>{ev.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Upcoming Actions */}
      {data.upcoming_actions.length > 0 && (
        <>
          <div className="section-title">Upcoming Actions</div>
          <div className="glass-card" style={{ padding: 20, marginBottom: 32 }}>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
              {data.upcoming_actions.map((a, i) => (
                <li
                  key={i}
                  style={{
                    padding: "10px 16px",
                    background: "rgba(34,211,238,0.04)",
                    borderRadius: "var(--radius-sm)",
                    borderLeft: "3px solid var(--accent-cyan)",
                    fontSize: "0.85rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  {a}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      {/* Quick Stats */}
      <div className="section-title">Quick Stats</div>
      <div className="stat-grid" style={{ marginBottom: 32 }}>
        {Object.entries(data.quick_stats).map(([k, v], i) => (
          <div key={i} className="glass-card stat-card">
            <div className="stat-card__label">{k}</div>
            <div className="stat-card__value">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
