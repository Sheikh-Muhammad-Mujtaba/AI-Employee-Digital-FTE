"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  fetchWhatsAppStatus,
  fetchWhatsAppQR,
  sendWhatsAppMessage,
  connectWhatsApp,
  disconnectWhatsApp,
  type WhatsAppStatus,
} from "@/lib/api";

export default function WhatsAppPage() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);

  // Send form
  const [jid, setJid] = useState("");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState("");

  const loadStatus = async () => {
    try {
      const s = await fetchWhatsAppStatus();
      setStatus(s);
      setError("");

      // Auto-fetch QR if pending
      if (s.status === "qr_pending" || s.qr_available) {
        const qrData = await fetchWhatsAppQR();
        setQr(qrData.qr);
      } else {
        setQr(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch status");
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      await connectWhatsApp();
      await loadStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Connect failed");
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setIsConnecting(true);
    try {
      if (confirm("Are you sure? This will log out and require a new QR scan.")) {
        await disconnectWhatsApp();
        await loadStatus();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Disconnect failed");
    } finally {
      setIsConnecting(false);
    }
  };

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!jid.trim() || !text.trim()) return;
    setSending(true);
    setSendResult("");
    try {
      const formattedJid = jid.includes("@") ? jid : `${jid}@s.whatsapp.net`;
      const res = await sendWhatsAppMessage(formattedJid, text);
      setSendResult(
        res.dry_run
          ? "✅ Message logged (DRY RUN mode)"
          : "✅ Message sent successfully!"
      );
      setText("");
    } catch (err: unknown) {
      setSendResult(err instanceof Error ? `❌ ${err.message}` : "❌ Send failed");
    } finally {
      setSending(false);
    }
  };

  const statusColor =
    status?.status === "connected"
      ? "var(--accent-emerald)"
      : status?.status === "qr_pending"
      ? "var(--accent-amber)"
      : "var(--accent-rose)";

  const statusLabel =
    status?.status === "connected"
      ? "Connected"
      : status?.status === "qr_pending"
      ? "QR Code Pending"
      : status?.status === "offline"
      ? "Service Offline"
      : status?.status || "Unknown";

  return (
    <div>
      <h1 className="page-title">WhatsApp Automation</h1>
      <p className="page-subtitle">
        Powered by Baileys — monitor connection, send messages, and view incoming alerts.
      </p>

      {error && <div className="alert-banner">⚠️ {error}</div>}

      {/* Connection Status */}
      <div className="stat-grid">
        <div className="glass-card stat-card animate-in">
          <div className="stat-card__label">Connection</div>
          <div className="stat-card__value" style={{ color: statusColor, fontSize: "1.5rem" }}>
            <span
              className={`pulse-dot ${
                status?.status === "connected"
                  ? "pulse-dot--green"
                  : status?.status === "qr_pending"
                  ? "pulse-dot--yellow"
                  : "pulse-dot--red"
              }`}
              style={{ display: "inline-block", marginRight: 10, verticalAlign: "middle" }}
            />
            {statusLabel}
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            {status?.status === "disconnected" && (
                <button className="btn-primary" style={{ padding: "4px 12px", fontSize: "0.8rem" }} onClick={handleConnect} disabled={isConnecting}>
                  {isConnecting ? "..." : "Connect"}
                </button>
            )}
            {(status?.status === "connected" || status?.status === "qr_pending") && (
                <button className="btn-danger" style={{ padding: "4px 12px", fontSize: "0.8rem" }} onClick={handleDisconnect} disabled={isConnecting}>
                  {isConnecting ? "..." : "Disconnect"}
                </button>
            )}
          </div>
        </div>

        <div className="glass-card stat-card animate-in animate-in-delay-1">
          <div className="stat-card__label">Mode</div>
          <div className="stat-card__value" style={{ fontSize: "1.5rem" }}>
            {status?.dry_run ? (
              <span className="badge badge--warn">DRY RUN</span>
            ) : (
              <span className="badge badge--ok">LIVE</span>
            )}
          </div>
        </div>

        <div className="glass-card stat-card animate-in animate-in-delay-2">
          <div className="stat-card__label">Keywords</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
            {(Array.isArray(status?.keywords) ? status.keywords : [status?.keywords].filter(Boolean)).map((kw, i) => (
              <span key={i} className="badge badge--idle">
                {String(kw)}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* QR Code Section */}
      {qr && (
        <div className="glass-card animate-in" style={{ padding: 28, marginBottom: 32, textAlign: "center" }}>
          <div className="section-title">📱 Scan QR Code to Link WhatsApp</div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 16 }}>
            Open WhatsApp → Linked Devices → Link a Device → Scan this code
          </p>
          <div
            style={{
              background: "white",
              padding: 24,
              borderRadius: "var(--radius-md)",
              display: "inline-block",
            }}
          >
            {/* Render QR as an image using the Data URL */}
            {qr && qr.startsWith("data:image") ? (
              <img
                src={qr}
                alt="WhatsApp QR Code"
                style={{ width: 256, height: 256, display: "block" }}
              />
            ) : (
              <div style={{ width: 256, height: 256, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>
                Generating...
              </div>
            )}
          </div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: 12 }}>
            QR refreshes automatically. You can also scan from the terminal where Baileys is running.
          </p>
        </div>
      )}

      {/* Send Message */}
      <div className="section-title">Send Message</div>
      <div className="glass-card animate-in" style={{ padding: 28, marginBottom: 32 }}>
        <form
          onSubmit={handleSend}
          style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 540 }}
        >
          <div>
            <label
              style={{
                display: "block",
                fontSize: "0.8rem",
                color: "var(--text-muted)",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              Phone Number (with country code, no + or spaces)
            </label>
            <input
              className="input-field"
              placeholder="e.g. 923001234567"
              value={jid}
              onChange={(e) => setJid(e.target.value)}
              required
            />
          </div>
          <div>
            <label
              style={{
                display: "block",
                fontSize: "0.8rem",
                color: "var(--text-muted)",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              Message
            </label>
            <textarea
              className="input-field"
              placeholder="Type your message…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              style={{ resize: "vertical" }}
              required
            />
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button
              type="submit"
              className="btn-primary"
              disabled={sending || status?.status !== "connected"}
            >
              {sending ? "Sending…" : "📤 Send Message"}
            </button>
            {status?.status !== "connected" && (
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                Connect WhatsApp first
              </span>
            )}
          </div>
          {sendResult && (
            <div
              style={{
                padding: "10px 16px",
                borderRadius: "var(--radius-sm)",
                background: sendResult.startsWith("✅")
                  ? "rgba(52,211,153,0.1)"
                  : "rgba(251,113,133,0.1)",
                color: sendResult.startsWith("✅")
                  ? "var(--accent-emerald)"
                  : "var(--accent-rose)",
                fontSize: "0.85rem",
              }}
            >
              {sendResult}
            </div>
          )}
        </form>
      </div>

      {/* Service Info */}
      {status?.error && (
        <div className="alert-banner" style={{ borderLeftColor: "var(--accent-rose)" }}>
          🔴 {status.error}
        </div>
      )}

      <div
        className="glass-card"
        style={{ padding: 20, fontSize: "0.82rem", color: "var(--text-muted)" }}
      >
        <strong style={{ color: "var(--text-secondary)" }}>How it works:</strong>
        <ul style={{ marginTop: 8, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
          <li>
            1️⃣ Start the Baileys service:{" "}
            <code style={{ color: "var(--accent-cyan)" }}>cd whatsapp-baileys && npm start</code>
          </li>
          <li>2️⃣ Scan the QR code to link your WhatsApp account</li>
          <li>
            3️⃣ Incoming messages matching keywords are saved to{" "}
            <code style={{ color: "var(--accent-cyan)" }}>AI_Employee_Vault/Needs_Action/</code>
          </li>
          <li>4️⃣ The orchestrator picks them up and processes via Claude</li>
        </ul>
      </div>
    </div>
  );
}
