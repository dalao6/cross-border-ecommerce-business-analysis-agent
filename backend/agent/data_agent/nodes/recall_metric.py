"""
指标召回步骤

负责根据关键词召回候选业务指标。优先走 Qdrant 向量检索，向量后端不可用时回退到 scoring.py。

返回：(指标 dict 列表, 指标实体列表)
"""

from backend.agent.data_agent.recall_backend import (
    is_vector_backend_available,
    mark_vector_backend_unavailable,
    metric_entity_to_dict,
)


async def recall_metric(query: str, keywords: list[str]) -> tuple[list[dict], list[dict]]:
    """召回与问题相关的业务指标。返回 (dict 列表, 实体列表)。"""
    if is_vector_backend_available():
        try:
            entities = await _vector_recall(keywords)
            if entities:
                return [metric_entity_to_dict(m) for m in entities], entities
        except Exception:  # noqa: BLE001
            mark_vector_backend_unavailable()

    # scoring 回退
    from backend.tools.metric_recall import metric_recall as metric_recall_scoring

    dicts = metric_recall_scoring(query)
    return dicts, []


async def _vector_recall(keywords: list[str]) -> list:
    """Qdrant 向量召回指标元数据，返回 MetricInfo 实体列表。"""
    from backend.clients.embedding_client_manager import embedding_client_manager
    from backend.clients.qdrant_client_manager import qdrant_client_manager
    from backend.repositories.qdrant.metric_qdrant_repository import (
        MetricQdrantRepository,
    )

    repo = MetricQdrantRepository(qdrant_client_manager.client)
    embedding_client = embedding_client_manager.client

    metric_map = {}
    for keyword in keywords:
        embedding = await embedding_client.aembed_query(keyword)
        current_metrics = await repo.search(embedding)
        for metric in current_metrics:
            if metric.id not in metric_map:
                metric_map[metric.id] = metric

    return list(metric_map.values())
