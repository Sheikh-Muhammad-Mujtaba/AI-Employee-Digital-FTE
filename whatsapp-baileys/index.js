/**
 * WhatsApp Watcher & Automation — Baileys v7
 *
 * This service:
 * 1. Connects to WhatsApp via QR code (first run) or saved credentials (reconnect).
 * 2. Watches incoming messages for configurable keywords.
 * 3. Writes urgent/matching messages as .md files into AI_Employee_Vault/Needs_Action/.
 * 4. Exposes a simple HTTP API (port 3001) so the orchestrator or dashboard can
 *    send messages or check connection status.
 *
 * Usage:
 *   npm start                       # starts watcher
 *   node index.js --vault ../AI_Employee_Vault
 */

import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from "baileys";
import pino from "pino";
import QRCode from "qrcode";
import { createServer } from "node:http";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// ── Config ────────────────────────────────────────────────────────────────────
import { dirname } from "node:path";
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const VAULT_PATH = resolve(__dirname, "..", "AI_Employee_Vault");
const AUTH_DIR = join(__dirname, "auth_info");
const NEEDS_ACTION = join(VAULT_PATH, "Needs_Action");
const LOGS_DIR = join(VAULT_PATH, "Logs");
const HTTP_PORT = parseInt(process.env.WA_HTTP_PORT || "3001", 10);
const DRY_RUN = process.env.DRY_RUN === "true";

// Keyword filtering removed: Agent now responds to ALL messages.

// Ensure directories exist
for (const dir of [NEEDS_ACTION, LOGS_DIR, AUTH_DIR]) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

const logger = pino({ level: "warn" });

// ── State ─────────────────────────────────────────────────────────────────────
let sock = null;
let connectionStatus = "disconnected";
let qrCode = null;

// ── Helpers ───────────────────────────────────────────────────────────────────

function sanitize(str) {
  return str.replace(/[^a-zA-Z0-9_-]/g, "_").substring(0, 60);
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function extractTextFromMessage(msg) {
  const m = msg.message;
  if (!m) return "";
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.documentMessage?.caption ||
    ""
  );
}

function getContactName(msg) {
  return msg.pushName || msg.key?.remoteJid?.split("@")[0] || "unknown";
}

function logEvent(event) {
  const today = new Date().toISOString().split("T")[0];
  const logFile = join(LOGS_DIR, `${today}.jsonl`);
  const entry = JSON.stringify({
    timestamp: new Date().toISOString(),
    source: "whatsapp_baileys",
    ...event,
  });
  try {
    writeFileSync(logFile, entry + "\n", { flag: "a" });
  } catch {
    // silently fail if log write fails
  }
}

function writeNeedsActionFile(senderName, senderJid, text, messageKey) {
  const ts = timestamp();
  const safeName = sanitize(senderName);
  const filename = `WHATSAPP_${safeName}_${ts}.md`;
  const filepath = join(NEEDS_ACTION, filename);

  const content = `---
type: whatsapp
from: ${senderName}
jid: ${senderJid}
received: ${new Date().toISOString()}
priority: high
status: pending
message_id: ${messageKey}
---

## WhatsApp Message

**From:** ${senderName} (${senderJid})
**Received:** ${new Date().toLocaleString()}

### Content
${text}

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Archive after processing
`;

  if (DRY_RUN) {
    console.log(`[DRY RUN] Would write: ${filename}`);
    logEvent({
      action_type: "whatsapp_ingest_dry_run",
      sender: senderName,
      jid: senderJid,
      filename,
    });
  } else {
    writeFileSync(filepath, content, "utf-8");
    console.log(`📝 Saved: ${filename}`);
    logEvent({
      action_type: "whatsapp_ingest",
      sender: senderName,
      jid: senderJid,
      filename,
    });
  }

  return filename;
}

// ── Connect ───────────────────────────────────────────────────────────────────

async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    logger,
    printQRInTerminal: false,
    // Browser identification shown to WhatsApp
    browser: ["AI Employee FTE", "Desktop", "1.0.0"],
  });

  // Save credentials whenever they update
  sock.ev.on("creds.update", saveCreds);

  // ── Connection management ───────────────────────────────────────────────
  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr: qrString } = update;

    if (qrString) {
      qrCode = qrString;
      connectionStatus = "qr_pending";
      console.log("\n📱 Scan the QR code above to link WhatsApp.\n");
    }

    if (connection === "open") {
      connectionStatus = "connected";
      qrCode = null;
      console.log("✅ WhatsApp connected successfully!");
      logEvent({ action_type: "whatsapp_connected" });
    }

    if (connection === "close") {
      connectionStatus = "disconnected";
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldRestart = statusCode !== DisconnectReason.loggedOut;

      if (shouldRestart) {
        console.log("🔄 Connection lost. Reconnecting in 5s…");
        logEvent({
          action_type: "whatsapp_reconnecting",
          reason: statusCode,
        });
        setTimeout(startWhatsApp, 5000);
      } else {
        console.log("❌ Logged out. Delete auth_info/ and restart to re-pair.");
        logEvent({ action_type: "whatsapp_logged_out" });
      }
    }
  });

  // ── Incoming messages ───────────────────────────────────────────────────
  sock.ev.on("messages.upsert", ({ type, messages }) => {
    if (type !== "notify") return; // only handle new real-time messages

    for (const msg of messages) {
      // Skip own messages and status broadcasts
      if (msg.key.fromMe) continue;
      if (msg.key.remoteJid === "status@broadcast") continue;

      const text = extractTextFromMessage(msg);
      if (!text) continue;

      const senderName = getContactName(msg);
      const senderJid = msg.key.remoteJid || "unknown";
      const lower = text.toLowerCase();

      console.log(`💬 ${senderName}: ${text.substring(0, 80)}…`);

      console.log(`💬 ${senderName}: ${text.substring(0, 80)}…`);

      // Write ALL messages to Needs_Action for the AI to analyze
      writeNeedsActionFile(
        senderName,
        senderJid,
        text,
        JSON.stringify(msg.key)
      );

      // Log every message regardless
      logEvent({
        action_type: "whatsapp_message_received",
        sender: senderName,
        jid: senderJid,
        text_preview: text.substring(0, 120),
        keyword_match: true, // Always true now
      });
    }
  });
}

// ── HTTP API ──────────────────────────────────────────────────────────────────
// Simple HTTP server so the orchestrator / dashboard can interact with WhatsApp.

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${HTTP_PORT}`);
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // GET /status — connection health check
  if (url.pathname === "/status" && req.method === "GET") {
    res.writeHead(200);
    res.end(
      JSON.stringify({
        status: connectionStatus,
        qr_available: !!qrCode,
        dry_run: DRY_RUN,
        keywords: "ALL (Removed)",
      })
    );
    return;
  }

  // GET /qr — get the current QR code string (for dashboard rendering)
  if (url.pathname === "/qr" && req.method === "GET") {
    res.writeHead(200);
    if (!qrCode) {
      res.end(JSON.stringify({ qr: null }));
    } else {
      try {
        const qrDataUrl = await QRCode.toDataURL(qrCode);
        res.end(JSON.stringify({ qr: qrDataUrl }));
      } catch (err) {
        console.error("QR Code Generation Error:", err);
        res.end(JSON.stringify({ error: err.message }));
      }
    }
    return;
  }

  // POST /send — send a text message
  //   body: { "jid": "923001234567@s.whatsapp.net", "text": "Hello!" }
  if (url.pathname === "/send" && req.method === "POST") {
    let body = "";
    for await (const chunk of req) body += chunk;

    try {
      const { jid, text } = JSON.parse(body);
      if (!jid || !text) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: "jid and text are required" }));
        return;
      }

      if (!sock || connectionStatus !== "connected") {
        res.writeHead(503);
        res.end(JSON.stringify({ error: "WhatsApp not connected" }));
        return;
      }

      if (DRY_RUN) {
        console.log(`[DRY RUN] Would send to ${jid}: ${text}`);
        logEvent({
          action_type: "whatsapp_send_dry_run",
          jid,
          text_preview: text.substring(0, 120),
        });
        res.writeHead(200);
        res.end(JSON.stringify({ success: true, dry_run: true }));
        return;
      }

      await sock.sendMessage(jid, { text });
      logEvent({
        action_type: "whatsapp_send",
        jid,
        text_preview: text.substring(0, 120),
      });
      res.writeHead(200);
      res.end(JSON.stringify({ success: true }));
    } catch (err) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // POST /connect — manual reconnect
  if (url.pathname === "/connect" && req.method === "POST") {
    if (connectionStatus === "connected" || connectionStatus === "qr_pending") {
      res.writeHead(400);
      res.end(JSON.stringify({ error: "Already connecting or connected" }));
      return;
    }
    console.log("🔄 Manual connection requested via API");
    startWhatsApp();
    res.writeHead(200);
    res.end(JSON.stringify({ success: true, status: "connecting" }));
    return;
  }

  // POST /disconnect — manual logout
  if (url.pathname === "/disconnect" && req.method === "POST") {
    if (sock) {
      console.log("🛑 Manual disconnect requested via API");
      // Use logout() to wipe existing credentials to get a fresh QR on next start
      sock.logout();
      sock = null;
    }
    qrCode = null;
    connectionStatus = "disconnected";
    res.writeHead(200);
    res.end(JSON.stringify({ success: true, status: "disconnected" }));
    return;
  }

  // 404
  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not found" }));
});

// ── Boot ──────────────────────────────────────────────────────────────────────
function startServer(port) {
  server.listen(port, () => {
    console.log(`\n🤖 WhatsApp Baileys Watcher`);
    console.log(`   Vault:     ${VAULT_PATH}`);
    console.log(`   HTTP API:  http://localhost:${port}`);
    console.log(`   DRY_RUN:   ${DRY_RUN}`);
    console.log(`   Keywords:  Accepting ALL messages\n`);
    startWhatsApp();
  });
}

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.warn(`Port ${HTTP_PORT} is already in use. Trying next port.`);
    const fallbackPort = HTTP_PORT + 1;
    server.close();
    server.listen(fallbackPort, () => {
      console.log(`\n🤖 WhatsApp Baileys Watcher started on fallback port ${fallbackPort}`);
      console.log(`   Vault:     ${VAULT_PATH}`);
      console.log(`   HTTP API:  http://localhost:${fallbackPort}`);
      console.log(`   DRY_RUN:   ${DRY_RUN}`);
      console.log(`   Keywords:  Accepting ALL messages\n`);
      startWhatsApp();
    });
  } else {
    console.error("WhatsApp server error:", err);
    process.exit(1);
  }
});

startServer(HTTP_PORT);
