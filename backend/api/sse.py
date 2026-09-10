"""SSE 消息封装。

把编排器产出的事件字典格式化为标准 SSE 文本（data: <json>\n\n）。
事件构造统一收敛到 shared.sse（event / make_event），这里只保留传输层格式化。
"""

import json

from backend.agent.shared.sse import event  # noqa: F401  # 向后兼容 re-export


def format_sse(event: dict) -> str:
    """将事件字典转为一条 SSE 消息。"""
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
