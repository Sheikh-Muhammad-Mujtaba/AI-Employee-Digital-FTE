"use client";
import { useState } from "react";
import { createPlanRequest } from "@/lib/api";

export default function PlanningPage() {
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setMessage("");
    try {
      const res = await createPlanRequest(prompt);
      setMessage(`Success! ${res.message}. The AI is now drafting your plan. Please check the Tasks tab shortly to approve it.`);
      setPrompt("");
    } catch (err: any) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">AI Planning</h1>
      <p className="page-subtitle">Describe a project or campaign, and your AI agent will draft a structured plan for you.</p>

      <div className="glass-card animate-in" style={{ padding: 28 }}>
        <form onSubmit={handleSubmit}>
          <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 8 }}>
            What do you want to plan?
          </label>
          <textarea
            className="input-field"
            style={{ width: "100%", height: 120, marginBottom: 16 }}
            placeholder="E.g., I want to launch a 3-week marketing campaign for our new feature release. It should include emails and social media posts."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={submitting}
          />
          <button type="submit" className="btn-primary" disabled={!prompt.trim() || submitting}>
            {submitting ? "Sending Request..." : "Generate AI Plan"}
          </button>
        </form>
        {message && <div style={{ marginTop: 16, color: message.startsWith("Error") ? "var(--accent-amber)" : "var(--accent-emerald)" }}>{message}</div>}
      </div>
    </div>
  );
}
