"""
请求上下文

用 ContextVar 保存一次请求的 request_id，让并发协程之间的 request_id 互不干扰。
本文件从 shopkeeper-agent 对齐移植而来。
"""

from contextvars import ContextVar

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="1")
