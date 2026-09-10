"""运行日志（shared 层）：把每次问数的关键事件打印到终端。

每条日志一行，统一前缀 `[yiyi-agent]`，kv 结构便于 grep / awk / 接入 Loki 等。
通过 `RunLog` 上下文对象在编排器与各 Agent 之间传递 request_id 与累计 token 用量。
"""

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenUsage:
    """LLM token 用量累计（OpenAI 兼容 usage 字段）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: dict | None) -> None:
        if not usage:
            return
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)


@dataclass
class RunLog:
    """单次问数的运行日志上下文。

    request_id 是 8 位 hex 前缀（保留可读性，便于终端快速锁定一次请求）。
    events 列表收集结构化事件，最终可被审计 / 监控消费。
    """

    request_id: str
    query: str
    started_at: float = field(default_factory=time.time)
    intent: str = ""
    tools: list[str] = field(default_factory=list)
    sql: str = ""
    external_sources: list[str] = field(default_factory=list)
    error_msg: str = ""
    tokens: TokenUsage = field(default_factory=TokenUsage)
    events: list[dict[str, Any]] = field(default_factory=list)
    finished_at: float = 0.0

    # ------------------------------------------------------------------ 打印

    @staticmethod
    def _ts() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _emit(self, level: str, msg: str, **kv: Any) -> None:
        """打印一行结构化日志到 stdout。"""
        parts = [
            f"[{self._ts()}]",
            "[yiyi-agent]",
            f"[req={self.request_id}]",
            f"[{level}]",
        ]
        if msg:
            parts.append(msg)
        for k, v in kv.items():
            if v is None or v == "":
                continue
            parts.append(f"{k}={_fmt(v)}")
        line = " ".join(parts)
        print(line, file=sys.stdout, flush=True)
        # 同步收集结构化事件，便于审计/监控消费
        self.events.append({
            "ts": self.started_at,
            "level": level,
            "msg": msg,
            "kv": {k: _safe(v) for k, v in kv.items() if v not in (None, "")},
        })

    # ------------------------------------------------------------ 公共接口

    def info(self, msg: str, **kv: Any) -> None:
        self._emit("INFO", msg, **kv)

    def warn(self, msg: str, **kv: Any) -> None:
        self._emit("WARN", msg, **kv)

    def error(self, msg: str, **kv: Any) -> None:
        self._emit("ERROR", msg, **kv)

    def tool_called(self, tool: str, **kv: Any) -> None:
        """记录一次工具调用。"""
        self._emit("TOOL", f"call {tool}", tool=tool, **kv)

    def finish(self, status: str = "ok") -> None:
        """打印结束汇总行（必含 token 用量与耗时）。"""
        self.finished_at = time.time()
        duration_ms = int((self.finished_at - self.started_at) * 1000)
        self._emit(
            "DONE" if status == "ok" else "FAIL",
            f"{status.upper()} query=\"{self._short(self.query)}\"",
            intent=self.intent,
            tools=",".join(self.tools),
            sql_len=len(self.sql),
            external_count=len(self.external_sources),
            prompt_tokens=self.tokens.prompt_tokens,
            completion_tokens=self.tokens.completion_tokens,
            total_tokens=self.tokens.total_tokens,
            duration_ms=duration_ms,
        )

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "intent": self.intent,
            "tools": self.tools,
            "sql": self.sql,
            "external_sources": self.external_sources,
            "error": self.error_msg,
            "tokens": {
                "prompt_tokens": self.tokens.prompt_tokens,
                "completion_tokens": self.tokens.completion_tokens,
                "total_tokens": self.tokens.total_tokens,
            },
            "duration_ms": int((self.finished_at - self.started_at) * 1000) if self.finished_at else 0,
            "events": self.events,
        }

    @staticmethod
    def _short(s: str, n: int = 60) -> str:
        s = (s or "").replace("\n", " ").strip()
        return s if len(s) <= n else s[:n] + "..."


def _fmt(v: Any) -> str:
    """kv 值格式化：字符串加引号、列表用 JSON、None/空跳过。"""
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        # 简化：列表转 JSON 字符串
        return json.dumps(list(v), ensure_ascii=False)
    return str(v)


def _safe(v: Any) -> Any:
    """to_dict 用的安全序列化。"""
    if isinstance(v, str):
        return v[:500]
    if isinstance(v, list):
        return v[:50]
    return v


def new_run_log(query: str) -> RunLog:
    """构造一个新的 RunLog，request_id 取 8 位 hex。"""
    import uuid
    return RunLog(request_id=uuid.uuid4().hex[:8], query=query)


# 终端启动横幅
def print_banner() -> None:
    print("=" * 60, file=sys.stdout, flush=True)
    print("[yiyi-agent] 启动日志：每次问数都会打印 req_id 与 token 用量", file=sys.stdout, flush=True)
    print("[yiyi-agent] 日志前缀：[ts] [yiyi-agent] [req=xxxxxxxx] [LEVEL] ...", file=sys.stdout, flush=True)
    print("=" * 60, file=sys.stdout, flush=True)
