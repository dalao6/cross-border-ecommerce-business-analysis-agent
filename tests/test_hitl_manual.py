"""HITL manual 模式冒烟测试：验证高风险操作中断 + Command(resume) 恢复。

运行：HITL_MODE=manual python tests/test_hitl_manual.py
"""

import os
os.environ.setdefault("HITL_MODE", "manual")

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent.orchestrator import Orchestrator  # noqa: E402


async def main():
    # ---- approve 流程 ----
    orch = Orchestrator()
    thread_id = None
    async for e in orch.run("哪个SKU未来15天可能缺货？"):
        if e["event"] == "hitl_pending":
            thread_id = e["data"]["thread_id"]
            print("[PASS] 高风险操作触发 HITL 中断:", e["data"].get("reason"))
            break
    assert thread_id, "manual 模式应中断等待审核"

    answer = None
    async for e in orch.resume(thread_id, "approve"):
        if e["event"] == "answer_generated":
            answer = e["data"]["answer"]
    assert answer is not None, "resume 后应产出答案"
    print("[PASS] 人工 approve 后继续执行，产出答案:", answer["summary"][:50])

    # ---- reject 流程 ----
    orch2 = Orchestrator()
    tid2 = None
    async for e in orch2.run("哪个SKU未来15天可能缺货？"):
        if e["event"] == "hitl_pending":
            tid2 = e["data"]["thread_id"]
            break
    rejected = False
    async for e in orch2.resume(tid2, "reject"):
        if e["event"] == "error":
            rejected = True
    print("[PASS] 人工 reject 后中止执行:", rejected)
    assert rejected, "reject 应产生 error 事件"


if __name__ == "__main__":
    asyncio.run(main())
    print("HITL manual 冒烟测试通过 ✅")
