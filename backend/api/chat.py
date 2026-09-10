"""问数查询接口。

POST /api/query           —— 接收自然语言问题，以 SSE 流式返回 Agent 执行轨迹与最终答案。
POST /api/query/confirm   —— Human-in-the-Loop 人工审核确认（manual 模式暂停后继续）。
GET  /api/health          —— 健康检查。
GET  /api/samples         —— 返回推荐样例问题（供前端首页展示）。
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent.orchestrator import Orchestrator
from backend.api.sse import format_sse

chat_router = APIRouter()

SAMPLE_QUESTIONS = [
    "2025年各月销量变化趋势如何？",
    "为什么我们2025年美国市场销量下降？",
    "TikTok Shop最近有什么规则变化，会不会影响我们的销量？",
    "哪个SKU未来15天可能缺货？",
    "搜索亚马逊,temu,eBay的情趣内衣热销榜的链接",
    "亚马逊和eBay情趣内衣有哪些？要看价格和月销",
    "我们Temu上卖的蕾丝套装和亚马逊热销款相比怎么样？",
    "今年B端客户复购率是多少？",
    "哪些产品质检不合格率最高？",
    "最近三个月哪个产品交付最慢？",
]

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class QueryRequest(BaseModel):
    query: str


class ConfirmRequest(BaseModel):
    thread_id: str
    decision: str = "approve"  # approve | reject


@chat_router.post("/api/query")
async def query_handler(req: QueryRequest):
    """接收问题，流式返回 Agent 执行过程。"""
    orchestrator = Orchestrator()

    async def stream():
        async for e in orchestrator.run(req.query):
            yield format_sse(e)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@chat_router.post("/api/query/confirm")
async def confirm_handler(req: ConfirmRequest):
    """Human-in-the-Loop 人工审核确认：恢复被暂停的会话。"""
    orchestrator = Orchestrator()

    async def stream():
        async for e in orchestrator.resume(req.thread_id, req.decision):
            yield format_sse(e)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@chat_router.get("/api/health")
async def health():
    return {"status": "ok", "service": "yiyi-agent"}


@chat_router.get("/api/samples")
async def samples():
    return {"questions": SAMPLE_QUESTIONS}
