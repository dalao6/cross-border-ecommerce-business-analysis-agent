"""FastAPI 生命周期管理。

启动时 best-effort 初始化 MySQL / Qdrant / ES / Embedding 客户端，关闭时释放连接。
离线环境（未启动 Docker 或未安装可选依赖）自动跳过，召回链路回退到 scoring.py 关键词打分。

注意：所有外部客户端都采用「惰性 import + 失败降级」策略，保证在缺少
omegaconf / sqlalchemy / qdrant-client / elasticsearch / langchain-huggingface
等可选依赖时，服务仍能启动并走离线演示链路。
"""

import asyncio
from contextlib import asynccontextmanager

from backend.config import settings


def _log(msg: str) -> None:
    """统一启动日志输出（避免引入 loguru 依赖，保持离线可跑）。"""
    print(f"[lifespan] {msg}", flush=True)


def _init_mysql_clients() -> None:
    """初始化 MySQL 客户端（meta + dw）。失败不阻断启动。"""
    try:
        from backend.clients.mysql_client_manager import (
            dw_mysql_client_manager,
            meta_mysql_client_manager,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"MySQL 依赖未安装，跳过初始化（{exc}）")
        return
    try:
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()
    except Exception as exc:  # noqa: BLE001
        _log(f"MySQL 客户端初始化失败：{exc}")


def _init_vector_clients() -> bool:
    """初始化 Qdrant / ES / Embedding 客户端，返回是否全部初始化成功。"""
    if settings.vector_recall_backend == "off":
        _log("vector_recall_backend=off，跳过向量后端初始化")
        return False

    try:
        from backend.clients.embedding_client_manager import embedding_client_manager
        from backend.clients.es_client_manager import es_client_manager
        from backend.clients.qdrant_client_manager import qdrant_client_manager
    except Exception as exc:  # noqa: BLE001
        _log(f"向量召回可选依赖未安装，回退关键词打分（{exc}）")
        return False

    try:
        qdrant_client_manager.init()
        es_client_manager.init()
        embedding_client_manager.init()
    except Exception as exc:  # noqa: BLE001
        _log(f"向量后端初始化失败，回退关键词打分：{exc}")
        return False
    return True


async def _probe_vector_backend() -> bool:
    """探测 Qdrant / ES / Embedding 是否真实可达（带短超时，避免首请求长等待）。"""
    from backend.clients.embedding_client_manager import embedding_client_manager
    from backend.clients.es_client_manager import es_client_manager
    from backend.clients.qdrant_client_manager import qdrant_client_manager

    async def qdrant_ok():
        await asyncio.wait_for(qdrant_client_manager.client.get_collections(), timeout=3)

    async def es_ok():
        await asyncio.wait_for(es_client_manager.client.ping(), timeout=3)

    async def emb_ok():
        await asyncio.wait_for(embedding_client_manager.client.aembed_query("测试"), timeout=3)

    results = await asyncio.gather(qdrant_ok(), es_ok(), emb_ok(), return_exceptions=True)
    return all(not isinstance(r, Exception) for r in results)


def _reset_vector_clients() -> None:
    """把向量客户端置 None，让 recall_backend.is_vector_backend_available() 返回 False。"""
    try:
        from backend.clients.embedding_client_manager import embedding_client_manager
        from backend.clients.es_client_manager import es_client_manager
        from backend.clients.qdrant_client_manager import qdrant_client_manager
        embedding_client_manager.client = None
        es_client_manager.client = None
        qdrant_client_manager.client = None
    except Exception:  # noqa: BLE001
        pass


async def _close_clients() -> None:
    """释放所有客户端连接。"""
    try:
        from backend.clients.embedding_client_manager import embedding_client_manager
        from backend.clients.es_client_manager import es_client_manager
        from backend.clients.mysql_client_manager import (
            dw_mysql_client_manager,
            meta_mysql_client_manager,
        )
        from backend.clients.qdrant_client_manager import qdrant_client_manager
    except Exception:  # noqa: BLE001
        return

    for mgr in (
        meta_mysql_client_manager,
        dw_mysql_client_manager,
        qdrant_client_manager,
        es_client_manager,
        embedding_client_manager,
    ):
        try:
            close_fn = getattr(mgr, "close", None)
            if close_fn is not None:
                await close_fn()
        except Exception:  # noqa: BLE001
            pass


@asynccontextmanager
async def lifespan(app):
    _init_mysql_clients()

    if _init_vector_clients():
        if await _probe_vector_backend():
            _log("向量后端可用，启用 Qdrant/ES 向量召回")
        else:
            _log("向量后端不可达，召回回退到关键词打分")
            _reset_vector_clients()
    else:
        _log("未启用向量后端，召回使用关键词打分（离线模式）")

    yield

    await _close_clients()
