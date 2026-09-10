"""Agent Orchestrator —— 多 Agent 顶层编排器。

职责：
    1. 驱动 Supervisor 主管图（意图识别 → 任务分配 → HITL 审核 → 派发子 Agent → 汇总）
    2. 把各 Agent 节点产出的 SSE 执行轨迹逐条流式推送给前端
    3. 支持 Human-in-the-Loop：manual 模式高风险操作前中断，等待人工确认后经
       Command(resume) 继续执行
    4. 组装最终答案、写审计日志、打印终端运行日志（含 token 用量）
    5. 每次请求生成 request_id，便于终端 grep & 监控

这是「主管 + 子 Agent + HITL」多智能体架构的入口，而非一条写死的线性管道。
"""

from __future__ import annotations

import time
from typing import AsyncGenerator

from backend.agent.shared.run_logger import RunLog, new_run_log, print_banner
from backend.agent.shared.sse import event
from backend.audit import log_audit

# 模块级：保存进行中的 run_log 与 audit，供 HITL resume 使用（thread_id → 上下文）
_active_runs: dict[str, dict] = {}

_banner_printed = False


class Orchestrator:
    """一次问数的编排器（基于 Supervisor StateGraph + 多子 Agent）。"""

    def __init__(self):
        global _banner_printed
        if not _banner_printed:
            print_banner()
            _banner_printed = True
        # 懒加载主管图（首次访问触发编译）
        from backend.agent.supervisor.graph import get_supervisor_graph
        self._graph = get_supervisor_graph()

    # ---------------------------------------------------------------- 辅助

    @staticmethod
    def _config(thread_id: str, run_log: RunLog | None = None) -> dict:
        return {"configurable": {"thread_id": thread_id, "run_log": run_log}}

    @staticmethod
    def _new_audit(run_log: RunLog, query: str) -> dict:
        return {
            "request_id": run_log.request_id,
            "question": query,
            "intent": "",
            "retrieved_tables": [],
            "retrieved_columns": [],
            "metrics": [],
            "generated_sql": "",
            "validated": None,
            "external_tool_used": False,
            "external_sources": [],
            "final_answer": "",
            "execution_time_ms": 0,
            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    @staticmethod
    def _interrupt_payload(chunk: dict) -> dict:
        """从 astream 的 __interrupt__ chunk 里提取 interrupt payload。"""
        interrupts = chunk.get("__interrupt__", ())
        if interrupts:
            obj = interrupts[0]
            val = getattr(obj, "value", None)
            if isinstance(val, dict):
                return val
            return {"payload": val}
        return {}

    @staticmethod
    def _collect_delta(audit: dict, state_delta: dict) -> bool:
        """从节点增量里收集审计字段，返回是否出现 error。"""
        has_error = False
        if "intent" in state_delta:
            audit["intent"] = state_delta["intent"]
        if state_delta.get("retrieved_tables"):
            audit["retrieved_tables"] = state_delta["retrieved_tables"]
        if state_delta.get("retrieved_column_infos"):
            audit["retrieved_columns"] = [
                c.get("column_name") for c in state_delta["retrieved_column_infos"]
            ]
        if state_delta.get("retrieved_metric_infos"):
            audit["metrics"] = [
                m.get("metric_name") for m in state_delta["retrieved_metric_infos"]
            ]
        if state_delta.get("internal"):
            internal = state_delta["internal"]
            audit["generated_sql"] = internal.get("sql", "")
            audit["validated"] = True
        if state_delta.get("answer"):
            answer = state_delta["answer"]
            audit["final_answer"] = answer.get("summary", "")
            audit["intent"] = audit["intent"] or answer.get("intent", "")
        if state_delta.get("error"):
            has_error = True
        return has_error

    def _finalize(self, run_log: RunLog, audit: dict, started: float,
                  status: str, emitted: int) -> None:
        """收尾：同步 token 用量 + 耗时，写审计日志，打印 DONE。"""
        audit["tokens"] = {
            "prompt_tokens": run_log.tokens.prompt_tokens,
            "completion_tokens": run_log.tokens.completion_tokens,
            "total_tokens": run_log.tokens.total_tokens,
        }
        audit["execution_time_ms"] = int((time.time() - started) * 1000)
        audit["external_sources"] = run_log.external_sources
        audit["external_tool_used"] = bool(run_log.external_sources)
        run_log.finish(status=status)
        audit["run_log_events"] = run_log.events[-50:]
        audit["emitted_events"] = emitted
        audit["orchestrator"] = "multi_agent_hitl"
        log_audit(audit)

    # ---------------------------------------------------------------- 入口

    async def run(self, query: str) -> AsyncGenerator[dict, None]:
        """执行一次问数，逐事件产出 SSE。

        内部用 Supervisor StateGraph 驱动：主管识别意图、派发子 Agent，
        HITL manual 模式高风险操作前中断（yield hitl_pending 后结束本次 stream），
        待人工确认后经 resume() 继续。
        """
        started = time.time()
        query = query.strip()

        run_log: RunLog = new_run_log(query)
        run_log.info("request_received", query_len=len(query))

        thread_id = run_log.request_id
        audit = self._new_audit(run_log, query)
        _active_runs[thread_id] = {
            "run_log": run_log, "audit": audit, "started": started, "emitted": 0,
        }

        yield event("received", "已接收问题", data={"request_id": thread_id})

        status = "ok"
        pending = False
        try:
            initial_state = {
                "query": query,
                "events": [],
                "request_id": thread_id,
            }
            async for chunk in self._graph.astream(
                initial_state, config=self._config(thread_id, run_log), stream_mode="updates",
            ):
                if "__interrupt__" in chunk:
                    pending = True
                    payload = self._interrupt_payload(chunk)
                    _active_runs[thread_id]["status"] = "pending"
                    yield event(
                        "hitl_pending", "等待人工审核确认", status="pending",
                        data={"thread_id": thread_id, **payload},
                    )
                    run_log.warn("hitl_pending", thread_id=thread_id,
                                 reason=payload.get("reason", ""))
                    return
                for node_name, state_delta in chunk.items():
                    for evt in state_delta.get("events", []) or []:
                        _active_runs[thread_id]["emitted"] += 1
                        yield evt
                    if self._collect_delta(audit, state_delta):
                        status = "error"
        except Exception as exc:  # noqa: BLE001
            status = "error"
            run_log.error("pipeline_exception", error=str(exc)[:300])
            yield event("error", f"流水线异常：{exc}", status="error")
        finally:
            if not pending:
                info = _active_runs.pop(thread_id, None)
                emitted = info["emitted"] if info else 0
                self._finalize(run_log, audit, started, status, emitted)

    async def resume(self, thread_id: str, decision: str = "approve") -> AsyncGenerator[dict, None]:
        """人工审核后继续执行（HITL resume）。"""
        from langgraph.types import Command

        info = _active_runs.get(thread_id)
        if not info:
            yield event("error", "未找到待审核的会话，无法继续。", status="error")
            return

        run_log: RunLog = info["run_log"]
        audit: dict = info["audit"]
        started: float = info["started"]

        status = "ok"
        pending = False
        try:
            async for chunk in self._graph.astream(
                Command(resume=decision),
                config=self._config(thread_id, run_log),
                stream_mode="updates",
            ):
                if "__interrupt__" in chunk:
                    pending = True
                    payload = self._interrupt_payload(chunk)
                    yield event(
                        "hitl_pending", "等待人工审核确认", status="pending",
                        data={"thread_id": thread_id, **payload},
                    )
                    return
                for node_name, state_delta in chunk.items():
                    for evt in state_delta.get("events", []) or []:
                        info["emitted"] += 1
                        yield evt
                    if self._collect_delta(audit, state_delta):
                        status = "error"
        except Exception as exc:  # noqa: BLE001
            status = "error"
            run_log.error("pipeline_exception", error=str(exc)[:300])
            yield event("error", f"流水线异常：{exc}", status="error")
        finally:
            if not pending:
                _active_runs.pop(thread_id, None)
                self._finalize(run_log, audit, started, status, info["emitted"])
