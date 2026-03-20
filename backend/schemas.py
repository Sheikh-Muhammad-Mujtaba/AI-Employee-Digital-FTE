"""Pydantic request / response schemas."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────────
class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Dashboard ─────────────────────────────────────────────────────────────────
class ComponentStatus(BaseModel):
    name: str
    status: str
    last_check: str


class SocialQueueItem(BaseModel):
    platform: str
    queued: int
    posted: int
    last_post: str


class AccountingMetric(BaseModel):
    metric: str
    value: str
    last_sync: str


class InboxSummary(BaseModel):
    pending_inbox: int = 0
    needs_action: int = 0
    pending_approval: int = 0
    active_plans: int = 0
    completed_today: int = 0


class ActivityEvent(BaseModel):
    time: str
    event: str
    details: str


class DashboardResponse(BaseModel):
    last_updated: str
    version: str
    tier: str
    system_status: list[ComponentStatus]
    social_queue: list[SocialQueueItem]
    accounting: list[AccountingMetric]
    inbox_summary: InboxSummary
    recent_activity: list[ActivityEvent]
    upcoming_actions: list[str]
    quick_stats: dict[str, str]
    alerts: list[str]


# ── Tasks ─────────────────────────────────────────────────────────────────────
class TaskFile(BaseModel):
    filename: str
    folder: str
    frontmatter: dict
    body: str
    raw: str
    created: str


class TaskActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|revise|ignore|edit|force_approve|draft|process)$")
    feedback: Optional[str] = None
    source_folder: str = "Pending_Approval"
    content: Optional[str] = None


class TaskActionResponse(BaseModel):
    filename: str
    action: str
    destination: str
    success: bool


# ── Projects / Plans ──────────────────────────────────────────────────────────
class BusinessGoals(BaseModel):
    last_updated: str
    review_frequency: str
    revenue_target_monthly: str
    revenue_current_mtd: str
    key_metrics: list[dict]
    active_projects: list[str]
    subscription_audit_rules: list[str]


class CreatePlanRequest(BaseModel):
    title: str
    description: str
    steps: list[str]
    due_date: Optional[str] = None
