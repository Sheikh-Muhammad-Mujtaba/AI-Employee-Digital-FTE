"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchPendingTasks,
  fetchNeedsAction,
  fetchDoneTasks,
  fetchLogs,
  fetchPlans,
  taskAction,
  type TaskFile,
} from "@/lib/api";

type Tab = "pending" | "needs_action" | "done" | "plans" | "logs";

export default function TasksPage() {
  const [tab, setTab] = useState<Tab>("pending");
  const [tasks, setTasks] = useState<TaskFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [revisingTask, setRevisingTask] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");

  const [editingTask, setEditingTask] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [filter, setFilter] = useState<"all" | "email" | "whatsapp" | "socials" | "other">("all");

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      let data: TaskFile[];
      switch (tab) {
        case "pending":
          data = await fetchPendingTasks();
          break;
        case "needs_action":
          data = await fetchNeedsAction();
          break;
        case "done":
          data = await fetchDoneTasks();
          break;
        case "plans":
          data = await fetchPlans();
          break;
        case "logs":
          data = await fetchLogs();
          break;
      }
      setTasks(data);
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleAction = async (filename: string, action: "approve" | "reject" | "revise" | "ignore" | "edit" | "force_approve" | "draft" | "process") => {
    setActionLoading(filename);
    try {
      const fb = action === "revise" ? feedback : undefined;
      const content = action === "edit" ? editContent : undefined;
      const source = tab === "needs_action" ? "Needs_Action" : "Pending_Approval";

      // Show loading message for AI Draft action
      if (action === "draft") {
        alert(`🤖 AI is processing "${filename}"...\n\nThis may take 30-60 seconds.\nThe file will appear in Pending Approval when ready.`);
      }

      // Show processing message for Process action
      if (action === "process") {
        alert(`⚙️ Processing "${filename}"...\n\nAI is executing the action (sending email, posting to social, etc.)\nThis may take 30-60 seconds.`);
      }

      await taskAction(filename, action, fb, source, content);

      if (action !== "edit") {
        setTasks((prev) => prev.filter((t) => t.filename !== filename));
        // Show success message
        if (action === "draft") {
          alert(`✅ AI drafting started!\n\nCheck "Pending Approval" tab in 30-60 seconds to see the draft.`);
        } else if (action === "process") {
          alert(`✅ Processing complete!\n\nThe action has been executed (email sent, post published, etc.)\n\nFile moved to Done.`);
        } else if (action === "approve") {
          alert(`✅ Approved!\n\nThe action will be executed shortly.`);
        } else if (action === "reject") {
          alert(`✅ Rejected and moved to Rejected folder.`);
        }
      } else {
        setEditingTask(null);
        setEditContent("");
        await loadTasks();
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Action failed";
      alert(`❌ Error: ${errorMsg}\n\nPlease try again or check the logs for details.`);
    } finally {
      setActionLoading(null);
      setRevisingTask(null);
      setFeedback("");
    }
  };

  const submitRevision = async (filename: string) => {
    if (!feedback.trim()) return;
    setActionLoading(filename);
    try {
      await taskAction(filename, "revise", feedback);
      await loadTasks();
      setRevisingTask(null);
      setFeedback("");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Revision failed");
    } finally {
      setActionLoading(null);
    }
  };

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "needs_action", label: "🔔 Needs Action" },
    { key: "pending", label: "⏳ Pending Approval" },
    { key: "done", label: "📦 Done" },
    { key: "plans", label: "📋 Plans" },
    { key: "logs", label: "📜 Logs" },
  ];

  const filteredTasks = tasks.filter((task) => {
    if (filter === "all") return true;
    const typeOrAction = (task.frontmatter.type || task.frontmatter.action || "").toLowerCase();
    if (filter === "email") return typeOrAction.includes("email");
    if (filter === "whatsapp") return typeOrAction.includes("whatsapp");
    if (filter === "socials") {
      return (
        typeOrAction.includes("post_") ||
        typeOrAction.includes("linkedin") ||
        typeOrAction.includes("twitter") ||
        typeOrAction.includes("facebook") ||
        typeOrAction.includes("instagram")
      );
    }
    return (
      !typeOrAction.includes("email") &&
      !typeOrAction.includes("whatsapp") &&
      !typeOrAction.includes("post_") &&
      !typeOrAction.includes("linkedin") &&
      !typeOrAction.includes("twitter") &&
      !typeOrAction.includes("facebook") &&
      !typeOrAction.includes("instagram")
    );
  });

  return (
    <div>
      <h1 className="page-title">Task Review</h1>
      <p className="page-subtitle">Review, approve, or reject tasks from your AI Employee.</p>

      {/* Tab bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24, flexWrap: "wrap", gap: 16 }}>
        <div style={{ display: "flex", gap: 8 }}>
          {tabs.map((t) => (
            <button
              key={t.key}
              className={tab === t.key ? "btn-primary" : "btn-ghost"}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        
        {/* Filter */}
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginRight: 4 }}>Filter by:</span>
          {(["all", "whatsapp", "email", "socials", "other"] as const).map((f) => (
            <button
              key={f}
              className={`badge ${filter === f ? "badge--ok" : "badge--idle"}`}
              style={{ cursor: "pointer", border: filter === f ? "1px solid var(--accent-emerald)" : "none" }}
              onClick={() => setFilter(f)}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p style={{ color: "var(--text-muted)" }}>Loading tasks…</p>
      ) : filteredTasks.length === 0 ? (
        <div
          className="glass-card"
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--text-muted)",
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: 8 }}>📭</div>
          <p>No tasks in this category.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {filteredTasks.map((task) => (
            <div key={task.filename} className="glass-card animate-in" style={{ padding: 20 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div
                    style={{
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      marginBottom: 4,
                      fontSize: "0.95rem",
                    }}
                  >
                    {task.filename}
                  </div>
                  <div style={{ display: "flex", gap: 12, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {task.frontmatter.type && (
                      <span className="badge badge--idle">{task.frontmatter.type}</span>
                    )}
                    {task.frontmatter.priority && (
                      <span
                        className={`badge ${
                          task.frontmatter.priority === "high" ? "badge--warn" : "badge--idle"
                        }`}
                      >
                        {task.frontmatter.priority}
                      </span>
                    )}
                    <span>Created: {new Date(task.created).toLocaleString()}</span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {tab === "pending" && (
                    <>
                      {revisingTask === task.filename ? (
                        <>
                          <button
                            className="btn-ghost"
                            style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => {
                              setRevisingTask(null);
                              setFeedback("");
                            }}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="btn-primary"
                            style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => handleAction(task.filename, "process")}
                            title="Process this draft - AI will execute the action (send email, post to social, etc.)"
                          >
                            {actionLoading === task.filename ? "…" : "⚙️ Process"}
                          </button>
                          <button
                            className="btn-ghost"
                            style={{ padding: "8px 16px", fontSize: "0.8rem", color: "var(--accent-amber)" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => setRevisingTask(task.filename)}
                          >
                            Revise
                          </button>
                          <button
                            className="btn-danger"
                            style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => handleAction(task.filename, "reject")}
                          >
                            ✗ Reject
                          </button>
                        </>
                      )}
                    </>
                  )}
                  {tab === "needs_action" && (
                    <>
                      {editingTask === task.filename ? (
                        <button
                          className="btn-ghost"
                          style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                          disabled={actionLoading === task.filename}
                          onClick={() => {
                            setEditingTask(null);
                            setEditContent("");
                          }}
                        >
                          Cancel
                        </button>
                      ) : (
                        <>
                          <button
                            className="btn-primary"
                            style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => handleAction(task.filename, "force_approve")}
                          >
                            {actionLoading === task.filename ? "…" : "✓ Process"}
                          </button>
                          <button
                            className="btn-ghost"
                            style={{ padding: "8px 16px", fontSize: "0.8rem", color: "var(--accent-cyan)" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => {
                              setEditingTask(task.filename);
                              setEditContent(task.raw || task.body);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="btn-ghost"
                            style={{ padding: "8px 16px", fontSize: "0.8rem", color: "var(--accent-purple)", borderColor: "var(--accent-purple)" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => handleAction(task.filename, "draft")}
                            title="Trigger the AI agent to draft a reply or process this document."
                          >
                            {actionLoading === task.filename ? "…" : "🤖 AI Draft"}
                          </button>
                          <button
                            className="btn-danger"
                            style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                            disabled={actionLoading === task.filename}
                            onClick={() => handleAction(task.filename, "ignore")}
                          >
                            ✖ Ignore
                          </button>
                        </>
                      )}
                    </>
                  )}
                  <button
                    className="btn-ghost"
                    style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                    onClick={() => setExpanded(expanded === task.filename ? null : task.filename)}
                  >
                    {expanded === task.filename ? "▲ Hide" : "▼ View"}
                  </button>
                </div>
              </div>

              {/* Editing Expanded State */}
              {editingTask === task.filename && (
                <div style={{ marginTop: 16 }}>
                  <textarea
                    className="input-field"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={10}
                    style={{ width: "100%", fontFamily: "monospace", fontSize: "0.85rem", resize: "vertical", marginBottom: 8 }}
                  />
                  <button
                    className="btn-primary"
                    style={{ padding: "8px 16px", fontSize: "0.8rem" }}
                    disabled={actionLoading === task.filename}
                    onClick={() => handleAction(task.filename, "edit")}
                  >
                    {actionLoading === task.filename ? "Saving…" : "Save Changes"}
                  </button>
                </div>
              )}

              {expanded === task.filename && revisingTask !== task.filename && (
                <div className="task-detail">{task.body || "(empty body)"}</div>
              )}
              {revisingTask === task.filename && (
                <div className="task-detail" style={{ background: "rgba(0,0,0,0.1)" }}>
                  <label style={{ display: "block", marginBottom: 8, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    Provide instructions for the AI to rewrite this task:
                  </label>
                  <textarea
                    className="input-field"
                    style={{ width: "100%", height: 100, marginBottom: 16 }}
                    placeholder="E.g., Make this reply shorter and offer a 10% discount..."
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                  />
                  <button
                    className="btn-primary"
                    onClick={() => submitRevision(task.filename)}
                    disabled={!feedback.trim() || actionLoading === task.filename}
                  >
                    {actionLoading === task.filename ? "Submitting..." : "Send Revision to AI"}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
