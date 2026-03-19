"use client";
import { useState, useEffect } from "react";
import { fetchAccountingSnapshot, createAccountingRequest } from "@/lib/api";

export default function AccountingPage() {
  const [snapshot, setSnapshot] = useState("");
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchAccountingSnapshot()
      .then((res) => setSnapshot(res.content))
      .catch(() => setSnapshot("Failed to load snapshot."))
      .finally(() => setLoading(false));
  }, []);

  const handlePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setMessage("");
    try {
      const res = await createAccountingRequest(prompt);
      setMessage(`Success! ${res.message}. The AI agent is reviewing your request. Please check your Approved/Pending tasks for its report.`);
      setPrompt("");
    } catch (err: any) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Accounting</h1>
      <p className="page-subtitle">Manage invoices, review ERPNext data, and instruct your AI Accountant.</p>

      {/* Accounting Agent Prompt */}
      <div className="glass-card animate-in" style={{ padding: 28, marginBottom: 32 }}>
        <div className="section-title">Instruct AI Accountant</div>
        <form onSubmit={handlePrompt}>
          <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 8 }}>
            Ask the agent to review invoices, create an invoice, or generate a new snapshot:
          </label>
          <textarea
            className="input-field"
            style={{ width: "100%", height: 100, marginBottom: 16 }}
            placeholder="E.g., Review all unpaid invoices from this week and draft an email to the clients."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={submitting}
          />
          <button type="submit" className="btn-primary" disabled={!prompt.trim() || submitting}>
            {submitting ? "Sending Request..." : "Instruct AI Agent"}
          </button>
        </form>
        {message && <div style={{ marginTop: 16, color: message.startsWith("Error") ? "var(--accent-amber)" : "var(--accent-emerald)" }}>{message}</div>}
      </div>

      {/* Latest Snapshot */}
      <div className="glass-card animate-in" style={{ padding: 28 }}>
        <div className="section-title">Latest Accounting Snapshot</div>
        {loading ? (
          <p style={{ color: "var(--text-muted)" }}>Loading snapshot...</p>
        ) : (
          <pre style={{ 
            background: "rgba(0,0,0,0.2)", 
            padding: 16, 
            borderRadius: 8, 
            whiteSpace: "pre-wrap", 
            fontFamily: "monospace",
            fontSize: "0.85rem",
            color: "var(--text-primary)"
          }}>
            {snapshot}
          </pre>
        )}
      </div>
    </div>
  );
}
