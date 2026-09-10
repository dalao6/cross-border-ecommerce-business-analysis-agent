"""
元数据知识库构建脚本入口

相当于构建流程的 controller 层，负责接收命令行参数、初始化客户端、创建仓储和服务对象，
再把真正的构建任务调度到 MetaKnowledgeService。

本文件从 shopkeeper-agent 对齐移植而来，包名由 app 改为 backend。
"""

import argparse
import asyncio
from pathlib import Path

from backend.clients.embedding_client_manager import embedding_client_manager
from backend.clients.es_client_manager import es_client_manager
from backend.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from backend.clients.qdrant_client_manager import qdrant_client_manager
from backend.repositories.es.value_es_repository import ValueESRepository
from backend.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from backend.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from backend.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from backend.services.meta_knowledge_service import MetaKnowledgeService


async def build(config_path: Path):
    """初始化依赖并执行一次元数据知识构建"""

    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()

    async with (
        meta_mysql_client_manager.session_factory() as meta_session,
        dw_mysql_client_manager.session_factory() as dw_session,
    ):
        meta_mysql_repository = MetaMySQLRepository(meta_session)
        dw_mysql_repository = DWMySQLRepository(dw_session)
        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
        embedding_client = embedding_client_manager.client
        value_es_repository = ValueESRepository(es_client_manager.client)
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)

        meta_knowledge_service = MetaKnowledgeService(
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository,
            column_qdrant_repository=column_qdrant_repository,
            embedding_client=embedding_client,
            value_es_repository=value_es_repository,
            metric_qdrant_repository=metric_qdrant_repository,
        )

        await meta_knowledge_service.build(config_path)

    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", required=True)
    args = parser.parse_args()

    asyncio.run(build(Path(args.conf)))
