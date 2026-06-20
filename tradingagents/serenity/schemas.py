"""Pydantic 契约：serenity scan API 输入与结构化报告输出。

对应 ``docs/spec-serenity-research.md`` §5（API 契约）。所有字段名称遵循
SKILL.md 的"卡住的环节 / 产业链位置 / 排序原因 / 证据 / 主要风险"五段式。
"""
from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ResearchMode(str, Enum):
    theme_scan = "theme_scan"
    single_challenge = "single_challenge"
    candidate_compare = "candidate_compare"


class Market(str, Enum):
    a_share = "A-share"
    us = "US"
    hk = "HK"


class LLMOverrides(BaseModel):
    llm_provider: Optional[str] = None
    deep_think_llm: Optional[str] = None
    quick_think_llm: Optional[str] = None


class ScanRequest(BaseModel):
    mode: ResearchMode = ResearchMode.theme_scan
    market: Market
    theme: Optional[str] = None
    tickers: Optional[List[str]] = None
    time_window_months: int = Field(default=12, ge=1, le=60)
    llm_overrides: Optional[LLMOverrides] = None


class Scope(BaseModel):
    market: str
    theme: Optional[str] = None
    tickers: Optional[List[str]] = None
    time_window: str


class ValueChainLayer(BaseModel):
    name: str
    rank: int
    reason: str


class ScarceLayer(BaseModel):
    layer: str
    why_scarce: str
    evidence_strength: Literal["strong", "medium", "weak"]


class Evidence(BaseModel):
    claim: str
    source: str
    strength: Literal["primary", "media", "analysis", "social", "unverified"]


class ScorecardSummary(BaseModel):
    final: float
    verdict: str


class CompanyCandidate(BaseModel):
    ticker: str
    company: str
    chain_position: str
    classification: Literal[
        "controls_scarce_layer",
        "supplies_scarce_layer",
        "benefits_from_trend",
        "weak_control",
        "story_only",
    ]


class TopPriority(BaseModel):
    ticker: str
    company: str
    constrains_what: str
    chain_position: str
    rank_reason: str
    evidence: List[Evidence]
    main_risk: str
    score: Optional[ScorecardSummary] = None


class SerenityReport(BaseModel):
    scope: Scope
    system_change: str
    value_chain_layers: List[ValueChainLayer]
    scarce_layers: List[ScarceLayer]
    company_universe: List[CompanyCandidate]
    top_priorities: List[TopPriority]
    what_could_go_wrong: List[str]
    next_research_moves: List[str]


class ScanProgress(BaseModel):
    step: int
    total: int = 9
    stage: str


class ScanJob(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: ScanProgress
    result: Optional[SerenityReport] = None
    sources_consulted: int = 0
    candidates_inspected: int = 0
    trace_log: List[str] = []
    error: Optional[str] = None
    created_at: str
    updated_at: str
