const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Thin wrapper around fetch that handles auth headers and JSON parsing.
 */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("fte_token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    // Token expired – clear and redirect
    if (typeof window !== "undefined") {
      localStorage.removeItem("fte_token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

/* ── Auth ──────────────────────────────────────────────────────────────────── */

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function login(
  username: string,
  password: string
): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function seedAdmin(): Promise<{ message: string }> {
  return request<{ message: string }>("/api/auth/seed", { method: "POST" });
}

/* ── Dashboard ─────────────────────────────────────────────────────────────── */

export interface ComponentStatus {
  name: string;
  status: string;
  last_check: string;
}

export interface SocialQueueItem {
  platform: string;
  queued: number;
  posted: number;
  last_post: string;
}

export interface AccountingMetric {
  metric: string;
  value: string;
  last_sync: string;
}

export interface InboxSummary {
  pending_inbox: number;
  needs_action: number;
  pending_approval: number;
  active_plans: number;
  completed_today: number;
}

export interface ActivityEvent {
  time: string;
  event: string;
  details: string;
}

export interface DashboardData {
  last_updated: string;
  version: string;
  tier: string;
  system_status: ComponentStatus[];
  social_queue: SocialQueueItem[];
  accounting: AccountingMetric[];
  inbox_summary: InboxSummary;
  recent_activity: ActivityEvent[];
  upcoming_actions: string[];
  quick_stats: Record<string, string>;
  alerts: string[];
}

export async function fetchDashboard(): Promise<DashboardData> {
  return request<DashboardData>("/api/dashboard/status");
}

/* ── Tasks ─────────────────────────────────────────────────────────────────── */

export interface TaskFile {
  filename: string;
  folder: string;
  frontmatter: Record<string, string>;
  body: string;
  raw: string;
  created: string;
}

export async function fetchPendingTasks(): Promise<TaskFile[]> {
  return request<TaskFile[]>("/api/tasks/pending");
}

export async function fetchNeedsAction(): Promise<TaskFile[]> {
  return request<TaskFile[]>("/api/tasks/needs-action");
}

export async function fetchDoneTasks(): Promise<TaskFile[]> {
  return request<TaskFile[]>("/api/tasks/done");
}

export async function fetchApprovedTasks(): Promise<TaskFile[]> {
  return request<TaskFile[]>("/api/tasks/approved");
}

export async function fetchLogs(): Promise<TaskFile[]> {
  return request<TaskFile[]>("/api/tasks/logs");
}

export async function taskAction(
  filename: string,
  action: "approve" | "reject" | "revise" | "ignore" | "edit" | "force_approve" | "draft" | "process",
  feedback?: string,
  source_folder?: string,
  content?: string
): Promise<{ filename: string; action: string; destination: string; success: boolean }> {
  const bodyPayload: any = { action };
  if (feedback) bodyPayload.feedback = feedback;
  if (source_folder) bodyPayload.source_folder = source_folder;
  if (content !== undefined) bodyPayload.content = content;

  return request(`/api/tasks/${encodeURIComponent(filename)}/action`, {
    method: "POST",
    body: JSON.stringify(bodyPayload),
  });
}

/* ── Projects ──────────────────────────────────────────────────────────────── */

export interface BusinessGoals {
  last_updated: string;
  review_frequency: string;
  revenue_target_monthly: string;
  revenue_current_mtd: string;
  key_metrics: Record<string, string>[];
  active_projects: string[];
  subscription_audit_rules: string[];
}

export async function fetchBusinessGoals(): Promise<BusinessGoals> {
  return request<BusinessGoals>("/api/projects/goals");
}

export async function fetchPlans(): Promise<TaskFile[]> {
  return request<TaskFile[]>("/api/projects/plans");
}

export async function createPlan(data: {
  title: string;
  description: string;
  steps: string[];
  due_date?: string;
}): Promise<{ message: string; path: string }> {
  return request("/api/projects/plans", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function createPlanRequest(prompt: string): Promise<{ message: string; filename: string }> {
  return request("/api/projects/generate", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

/* ── Accounting ────────────────────────────────────────────────────────────── */

export async function createAccountingRequest(prompt: string): Promise<{ message: string; filename: string }> {
  return request("/api/accounting/request", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export async function fetchAccountingSnapshot(): Promise<{ content: string }> {
  return request<{ content: string }>("/api/accounting/snapshot");
}

/* ── WhatsApp ──────────────────────────────────────────────────────────────── */

export interface WhatsAppStatus {
  status: string;
  qr_available?: boolean;
  dry_run?: boolean;
  keywords?: string[];
  error?: string;
}

export async function fetchWhatsAppStatus(): Promise<WhatsAppStatus> {
  return request<WhatsAppStatus>("/api/whatsapp/status");
}

export async function fetchWhatsAppQR(): Promise<{ qr: string | null }> {
  return request<{ qr: string | null }>("/api/whatsapp/qr");
}

export async function sendWhatsAppMessage(
  jid: string,
  text: string
): Promise<{ success: boolean; dry_run?: boolean }> {
  return request("/api/whatsapp/send", {
    method: "POST",
    body: JSON.stringify({ jid, text }),
  });
}

export async function connectWhatsApp(): Promise<{ success: boolean }> {
  return request("/api/whatsapp/connect", {
    method: "POST",
  });
}

export async function disconnectWhatsApp(): Promise<{ success: boolean }> {
  return request("/api/whatsapp/disconnect", {
    method: "POST",
  });
}
