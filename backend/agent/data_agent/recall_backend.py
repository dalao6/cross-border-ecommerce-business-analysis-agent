"""
召回后端选择与向量召回辅助。

提供统一判断入口，让内部链路的召回步骤在「向量召回（Qdrant + ES + Embedding）」
与「关键词打分（scoring.py）」之间自动切换：

    - 配置 vector_recall_backend = off        → 永远走 scoring（完全离线）
    - 配置 vector_recall_backend = on         → 永远走向量召回
    - 配置 vector_recall_backend = auto（默认）→ 运行时检测，向量后端不可用自动回退 scoring

向量后端「不可用」的判断依据：客户端管理器未初始化（lifespan 未启动外部服务），
或首次向量召回抛出连接异常。一旦确认不可用，会缓存结果避免每次请求重复探测。
"""

from backend.config import settings

# 运行时缓存：向量后端一旦确认不可用就置 True，避免重复探测
_vector_unavailable = False


def vector_recall_disabled() -> bool:
    """是否显式禁用向量召回（off）。"""
    return settings.vector_recall_backend == "off"


def vector_recall_forced() -> bool:
    """是否强制向量召回（on）。"""
    return settings.vector_recall_backend == "on"


def is_vector_backend_available() -> bool:
    """向量后端是否可用（结合配置、客户端初始化状态与失败缓存）。"""
    global _vector_unavailable
    if vector_recall_disabled():
        return False
    if _vector_unavailable:
        return False

    # 客户端只有在 lifespan 里 init() 成功后才非 None
    try:
        from backend.clients.embedding_client_manager import embedding_client_manager
        from backend.clients.es_client_manager import es_client_manager
        from backend.clients.qdrant_client_manager import qdrant_client_manager
    except Exception:  # noqa: BLE001 —— 未安装可选依赖（omegaconf/langchain/qdrant/elasticsearch）时安全回退
        return False

    return bool(
        qdrant_client_manager.client is not None
        and embedding_client_manager.client is not None
        and es_client_manager.client is not None
    )


def mark_vector_backend_unavailable() -> None:
    """标记向量后端不可用，后续召回直接走 scoring 回退。"""
    global _vector_unavailable
    _vector_unavailable = True


def reset_vector_backend_state() -> None:
    """重置失败缓存（测试或重新连接时使用）。"""
    global _vector_unavailable
    _vector_unavailable = False


# ---------------------------------------------------------------------------
# 实体 → dict 转换（保持内部链路下游与 SSE 展示兼容的字段结构）
# ---------------------------------------------------------------------------
def column_entity_to_dict(column) -> dict:
    """ColumnInfo 实体 → schema_recall 兼容 dict。"""
    role = column.role or "dimension"
    return {
        "table_name": column.table_id,
        "column_name": column.name,
        "column_comment": column.name,
        "business_meaning": column.description or "",
        "data_type": column.type or "VARCHAR",
        "is_dimension": role == "dimension",
        "is_measure": role == "measure",
        "synonyms": column.alias or [],
    }


def metric_entity_to_dict(metric) -> dict:
    """MetricInfo 实体 → metric_recall 兼容 dict。"""
    tables = sorted({c.split(".")[0] for c in (metric.relevant_columns or []) if "." in c})
    columns = [c.split(".")[-1] for c in (metric.relevant_columns or []) if "." in c]
    return {
        "metric_name": metric.name,
        "metric_definition": metric.description or "",
        "formula": "",
        "related_tables": tables,
        "related_columns": columns,
        "business_domain": "",
        "synonyms": metric.alias or [],
    }


def table_entity_to_dict(table) -> dict:
    """TableInfo 实体 → table_recall 兼容 dict。"""
    return {
        "table_name": table.name,
        "table_comment": table.name,
        "business_domain": table.role or "",
        "business_description": table.description or "",
        "synonyms": [],
    }


# ---------------------------------------------------------------------------
# 向量召回实现（Qdrant / ES / Embedding）
# ---------------------------------------------------------------------------
async def recall_columns_by_vector(keywords: list[str]) -> list:
    """Qdrant 字段向量召回，返回 ColumnInfo 实体列表。"""
    from backend.clients.embedding_client_manager import embedding_client_manager
    from backend.clients.qdrant_client_manager import qdrant_client_manager
    from backend.repositories.qdrant.column_qdrant_repository import (
        ColumnQdrantRepository,
    )

    repo = ColumnQdrantRepository(qdrant_client_manager.client)
    embedding_client = embedding_client_manager.client

    column_map = {}
    for keyword in keywords:
        embedding = await embedding_client.aembed_query(keyword)
        current_columns = await repo.search(embedding)
        for column in current_columns:
            if column.id not in column_map:
                column_map[column.id] = column
    return list(column_map.values())


async def recall_metrics_by_vector(keywords: list[str]) -> list:
    """Qdrant 指标向量召回，返回 MetricInfo 实体列表。"""
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


async def recall_values_by_es(keywords: list[str]) -> list:
    """ES 全文检索字段取值，返回 ValueInfo 实体列表。"""
    from backend.clients.es_client_manager import es_client_manager
    from backend.repositories.es.value_es_repository import ValueESRepository

    repo = ValueESRepository(es_client_manager.client)

    value_map = {}
    for keyword in keywords:
        current_values = await repo.search(keyword)
        for value in current_values:
            if value.id not in value_map:
                value_map[value.id] = value
    return list(value_map.values())


async def recall_tables_by_vector(keywords: list[str]) -> list:
    """从字段向量召回结果中提取表名，返回 table_recall 兼容 dict 列表。"""
    columns = await recall_columns_by_vector(keywords)
    table_map = {}
    for column in columns:
        if column.table_id not in table_map:
            table_map[column.table_id] = {
                "table_name": column.table_id,
                "table_comment": column.table_id,
                "business_domain": "",
                "business_description": "",
                "synonyms": [],
            }
    return list(table_map.values())
