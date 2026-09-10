"""
Qdrant 客户端管理器

统一创建和管理 Qdrant 异步客户端，主要用于保存字段和指标的向量索引，支撑问数流程中的语义召回。
本文件从 shopkeeper-agent 对齐移植而来，包名由 app 改为 backend。
"""

import asyncio
import random
from typing import Optional

from qdrant_client import AsyncQdrantClient, models

from backend.conf.app_config import QdrantConfig, app_config


class QdrantClientManager:
    """管理 Qdrant 客户端的初始化与关闭"""

    def __init__(self, qdrant_config: QdrantConfig):
        self.qdrant_config = qdrant_config
        self.client: Optional[AsyncQdrantClient] = None

    def _get_url(self) -> str:
        return f"http://{self.qdrant_config.host}:{self.qdrant_config.port}"

    def init(self):
        self.client = AsyncQdrantClient(url=self._get_url())

    async def close(self):
        if self.client is not None:
            await self.client.close()


# 全局单例
qdrant_client_manager = QdrantClientManager(app_config.qdrant)


if __name__ == "__main__":
    qdrant_client_manager.init()

    async def test():
        client = qdrant_client_manager.client
        if not await client.collection_exists("my_collection"):
            await client.create_collection(
                collection_name="my_collection",
                vectors_config=models.VectorParams(
                    size=10,
                    distance=models.Distance.COSINE,
                ),
            )
        await client.upsert(
            collection_name="my_collection",
            points=[
                models.PointStruct(
                    id=i,
                    vector=[random.random() for _ in range(10)],
                )
                for i in range(100)
            ],
        )
        res = await client.query_points(
            collection_name="my_collection",
            query=[random.random() for _ in range(10)],  # type: ignore
            limit=10,
            score_threshold=0.8,
        )
        print(res)

    asyncio.run(test())
