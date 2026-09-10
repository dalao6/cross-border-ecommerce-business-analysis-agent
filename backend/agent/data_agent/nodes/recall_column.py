"""
字段召回步骤

负责根据关键词召回候选字段。优先走 Qdrant 向量检索（关键词 → Embedding → Qdrant），
向量后端不可用时回退到 scoring.py 关键词打分方案。

返回：(字段 dict 列表, 字段实体列表)
"""

from backend.agent.data_agent.recall_backend import (
    column_entity_to_dict,
    is_vector_backend_available,
    mark_vector_backend_unavailable,
    recall_columns_by_vector,
)


async def recall_column(
    query: str, keywords: list[str], retrieved_tables: list[str] | None = None
) -> tuple[list[dict], list[dict]]:
    """召回与问题相关的字段。返回 (dict 列表, 实体列表)。"""
    if is_vector_backend_available():
        try:
            entities = await recall_columns_by_vector(keywords)
            if entities:
                return [column_entity_to_dict(c) for c in entities], entities
        except Exception:  # noqa: BLE001
            mark_vector_backend_unavailable()

    # scoring 回退
    from backend.tools.schema_recall import schema_recall as schema_recall_scoring

    dicts = schema_recall_scoring(query, retrieved_tables)
    return dicts, []
