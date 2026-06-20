"""Serenity 主工作流：单 LLM agent + tool loop。

按 SKILL.md 9 步流程跑一次 ``langgraph.prebuilt.create_react_agent``，LLM 最终
输出 JSON 报告，parse + validate 成 ``SerenityReport``。整套**不接入项目本身的
LangGraph 多代理图**（``tradingagents.graph``），保持隔离（spec §4 决策）；
之所以仍走 ``langgraph.prebuilt``：项目栈只装了 ``langgraph`` 没装顶层
``langchain``，统一栈避免新增依赖。

进度回调形态：
- ``progress_cb(step: int, stage: str)`` 在工作流入口 / 出口 / 异常切换时触发
- ``trace_cb(line: str)`` 记录 tool 调用 / 响应等审计信息

LLM provider/model 优先取请求的 ``llm_overrides``，回退到环境变量
``TRADINGAGENTS_LLM_PROVIDER`` / ``TRADINGAGENTS_DEEP_THINK_LLM``——与
``DEFAULT_CONFIG`` 同一来源。
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from pydantic import ValidationError

from tradingagents.llm_clients import create_llm_client

from .prompts import build_system_prompt, build_user_message
from .schemas import ScanRequest, SerenityReport
from .tools import SERENITY_TOOLS

logger = logging.getLogger(__name__)


_PROGRESS_STAGES = [
    (1, "set_scope"),
    (2, "translate_story"),
    (3, "map_value_chain"),
    (4, "find_scarce_layer"),
    (5, "build_company_universe"),
    (6, "gather_evidence"),
    (7, "rank_priorities"),
    (8, "explain_risks"),
    (9, "next_research_moves"),
]


_DEFAULT_RECURSION_LIMIT = 60


class SerenityWorkflowError(Exception):
    """workflow 不可恢复错误（LLM 拿不到 / JSON 解析失败 / schema 不符）。"""


class _ProgressCallback(BaseCallbackHandler):
    """把 langgraph agent 的 tool 事件转成 trace_cb 行 + 计 source。

    SKILL.md 验收要求 ≥ 25 条来源、≥ 20 家候选，这里只统计"网络源 tool 调用次数"
    给前端一个粗略下限指标——不与"实际独立源数"严格对齐，但比让 LLM 自报更可靠。
    """

    def __init__(
        self,
        trace_cb: Optional[Callable[[str], None]] = None,
        sources_counter: Optional[list] = None,
    ):
        self.trace_cb = trace_cb or (lambda s: None)
        self.sources_counter = sources_counter if sources_counter is not None else [0]

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name", "tool")
        snippet = (input_str or "")[:120].replace("\n", " ")
        self.trace_cb(f"→ {name}({snippet})")
        if name in {"web_search", "get_filings_cn", "get_filings_us"}:
            self.sources_counter[0] += 1

    def on_tool_end(self, output, **kwargs):
        size = len(str(output or ""))
        self.trace_cb(f"← tool ok ({size}B)")

    def on_tool_error(self, error, **kwargs):
        self.trace_cb(f"⚠ tool error: {type(error).__name__}: {str(error)[:120]}")


def _resolve_llm(request: ScanRequest):
    ov = request.llm_overrides
    provider = (ov.llm_provider if ov else None) or os.environ.get(
        "TRADINGAGENTS_LLM_PROVIDER", "openai"
    )
    model = (ov.deep_think_llm if ov else None) or os.environ.get(
        "TRADINGAGENTS_DEEP_THINK_LLM", "gpt-4o"
    )
    backend_url = os.environ.get("TRADINGAGENTS_LLM_BACKEND_URL") or None
    client = create_llm_client(provider, model, base_url=backend_url)
    return client.get_llm()


def _build_agent(llm, tools, system_prompt: str):
    """create_react_agent 包一层，方便单测 patch。"""
    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _coalesce_content(content) -> str:
    """把可能是 list-of-blocks 的 message content 摊平成纯文本（OpenAI Responses / Gemini 3 形态）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    parts.append(b.get("text", ""))
            elif isinstance(b, str):
                parts.append(b)
        return "\n".join(p for p in parts if p)
    return str(content or "")


def parse_report(text: str) -> SerenityReport:
    """从 LLM 自由文本里抽 JSON 报告并 validate 成 ``SerenityReport``。

    依次尝试：
    1. ```json ...``` 代码块
    2. 第一个 `{` 到最后一个 `}` 的整段
    3. 文本本身就是 JSON
    """
    if not text:
        raise SerenityWorkflowError("LLM 返回空文本，无法解析报告")

    candidates: list[str] = []
    for m in _JSON_BLOCK_RE.finditer(text):
        candidates.append(m.group(1))
    if not candidates:
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            candidates.append(text[l : r + 1])
    candidates.append(text.strip())

    last_err: Optional[Exception] = None
    for cand in candidates:
        try:
            obj = json.loads(cand)
            return SerenityReport.model_validate(obj)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            continue
    raise SerenityWorkflowError(
        f"LLM 输出未能解析为合规 SerenityReport: "
        f"{type(last_err).__name__ if last_err else 'NoError'}: {last_err}"
    )


def run_serenity_workflow(
    request: ScanRequest,
    *,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    trace_cb: Optional[Callable[[str], None]] = None,
    llm=None,
    tools=None,
) -> tuple[SerenityReport, int]:
    """主入口。返回 ``(report, sources_count)``。

    ``llm`` / ``tools`` 可注入以方便单测；正常调用应留空走默认。
    """
    tools = tools if tools is not None else SERENITY_TOOLS
    llm = llm if llm is not None else _resolve_llm(request)

    progress_cb = progress_cb or (lambda step, stage: None)
    trace_cb = trace_cb or (lambda line: None)

    progress_cb(1, "set_scope")

    system = build_system_prompt(request.mode, request.market)
    user = build_user_message(
        request.mode,
        request.market,
        theme=request.theme,
        tickers=request.tickers,
        time_window_months=request.time_window_months,
    )

    sources_counter = [0]
    cb = _ProgressCallback(trace_cb=trace_cb, sources_counter=sources_counter)
    agent = _build_agent(llm, tools, system)

    progress_cb(2, "translate_story")
    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=user)]},
            config={
                "recursion_limit": _DEFAULT_RECURSION_LIMIT,
                "callbacks": [cb],
            },
        )
    except Exception as e:
        raise SerenityWorkflowError(
            f"agent loop 执行失败: {type(e).__name__}: {e}"
        ) from e

    messages = (result or {}).get("messages") if isinstance(result, dict) else None
    if not messages:
        raise SerenityWorkflowError("agent 返回空消息列表")
    last = messages[-1]
    output = _coalesce_content(getattr(last, "content", None) or getattr(last, "text", None) or "")

    progress_cb(9, "next_research_moves")
    report = parse_report(output)
    return report, sources_counter[0]


__all__ = [
    "SerenityWorkflowError",
    "parse_report",
    "run_serenity_workflow",
]
