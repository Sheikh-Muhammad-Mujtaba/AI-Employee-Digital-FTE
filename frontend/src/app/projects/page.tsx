"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  fetchBusinessGoals,
  fetchPlans,
  createPlan,
  type BusinessGoals,
  type TaskFile,
} from "@/lib/api";

export default function ProjectsPage() {
  const [goals, setGoals] = useState<BusinessGoals | null>(null);
  const [plans, setPlans] = useState<TaskFile[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [stepsText, setStepsText] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchBusinessGoals().then(setGoals).catch(() => {});
    fetchPlans().then(setPlans).catch(() => {});
  }, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      const steps = stepsText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      await createPlan({
        title,
        description,
        steps,
        due_date: dueDate || undefined,
      });
      // Refresh plans
      const refreshed = await fetchPlans();
      setPlans(refreshed);
      setShowForm(false);
      setTitle("");
      setDescription("");
      setStepsText("");
      setDueDate("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to create plan");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Projects & Plans</h1>
      <p className="page-subtitle">
        Business goals, revenue targets, and project planning.
      </p>

      {/* Business Goals */}
      {goals && (
        <div className="glass-card animate-in" style={{ padding: 28, marginBottom: 32 }}>
          <div className="section-title">Q1 2026 Business Goals</div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 20 }}>
            Last updated: {goals.last_updated} · Review frequency: {goals.review_frequency}
          </div>

          <div className="stat-grid">
            <div className="glass-card stat-card">
              <div className="stat-card__label">Monthly Revenue Target</div>
              <div className="stat-card__value" style={{ color: "var(--accent-emerald)" }}>
                {goals.revenue_target_monthly}
              </div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-card__label">Current MTD</div>
              <div className="stat-card__value" style={{ color: "var(--accent-cyan)" }}>
                {goals.revenue_current_mtd}
              </div>
            </div>
          </div>

          {/* Key Metrics */}
          {goals.key_metrics.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 10, fontSize: "0.9rem" }}>Key Metrics</div>
              <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      {Object.keys(goals.key_metrics[0]).map((k) => (
                        <th key={k}>{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {goals.key_metrics.map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((val, j) => (
                          <td key={j}>{val}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Active Projects */}
          {goals.active_projects.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 10, fontSize: "0.9rem" }}>Active Projects</div>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
                {goals.active_projects.map((p, i) => (
                  <li
                    key={i}
                    style={{
                      padding: "10px 16px",
                      background: "rgba(167,139,250,0.06)",
                      borderLeft: "3px solid var(--accent-purple)",
                      borderRadius: "var(--radius-sm)",
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Audit Rules */}
          {goals.subscription_audit_rules.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 10, fontSize: "0.9rem" }}>
                Subscription Audit Rules
              </div>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                {goals.subscription_audit_rules.map((r, i) => (
                  <li key={i} style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    • {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Plans Section */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div className="section-title" style={{ margin: 0 }}>
          Plans
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "✗ Cancel" : "+ New Plan"}
        </button>
      </div>

      {/* Create Plan Form */}
      {showForm && (
        <div className="glass-card animate-in" style={{ padding: 28, marginBottom: 24 }}>
          <form className="plan-form" onSubmit={handleCreate}>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 6 }}>
                PLAN TITLE
              </label>
              <input
                className="input-field"
                placeholder="e.g., Launch Social Campaign Q1"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 6 }}>
                DESCRIPTION
              </label>
              <textarea
                className="input-field"
                placeholder="Describe the project goal..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                style={{ resize: "vertical" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 6 }}>
                STEPS (one per line)
              </label>
              <textarea
                className="input-field"
                placeholder={`Research target audience\nCreate content calendar\nSchedule first batch of posts`}
                value={stepsText}
                onChange={(e) => setStepsText(e.target.value)}
                rows={5}
                style={{ resize: "vertical" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 6 }}>
                DUE DATE (optional)
              </label>
              <input
                type="date"
                className="input-field"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Creating…" : "Create Plan"}
            </button>
          </form>
        </div>
      )}

      {/* Existing Plans */}
      {plans.length === 0 ? (
        <div
          className="glass-card"
          style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}
        >
          <div style={{ fontSize: "2rem", marginBottom: 8 }}>📋</div>
          <p>No plans yet. Create one to get started.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {plans.map((plan) => (
            <div key={plan.filename} className="glass-card animate-in" style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.95rem" }}>
                    {plan.frontmatter.title || plan.filename}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>
                    {plan.frontmatter.status && (
                      <span className="badge badge--ok" style={{ marginRight: 8 }}>
                        {plan.frontmatter.status}
                      </span>
                    )}
                    Due: {plan.frontmatter.due_date || "TBD"} · Created:{" "}
                    {new Date(plan.created).toLocaleDateString()}
                  </div>
                </div>
                <button
                  className="btn-ghost"
                  style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                  onClick={() => setExpanded(expanded === plan.filename ? null : plan.filename)}
                >
                  {expanded === plan.filename ? "▲ Hide" : "▼ View"}
                </button>
              </div>
              {expanded === plan.filename && (
                <div className="task-detail">{plan.body || "(empty body)"}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
