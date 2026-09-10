"""
Elasticsearch 客户端管理器

统一创建和管理 Elasticsearch 异步客户端，主要服务于字段真实取值的全文索引构建和检索。
本文件从 shopkeeper-agent 对齐移植而来，包名由 app 改为 backend。
"""

import asyncio
from typing import Optional

from elasticsearch import AsyncElasticsearch

from backend.conf.app_config import ESConfig, app_config


class ESClientManager:
    """管理 Elasticsearch 客户端的生命周期"""

    def __init__(self, es_config: ESConfig):
        self.es_config = es_config
        self.client: Optional[AsyncElasticsearch] = None

    def _get_url(self) -> str:
        return f"http://{self.es_config.host}:{self.es_config.port}"

    def init(self):
        self.client = AsyncElasticsearch(hosts=[self._get_url()])

    async def close(self):
        if self.client is not None:
            await self.client.close()


# 全局可复用单例
es_client_manager = ESClientManager(app_config.es)


if __name__ == "__main__":
    es_client_manager.init()

    async def test():
        client = es_client_manager.client
        try:
            if not await client.indices.exists(index="my-books"):
                await client.indices.create(
                    index="my-books",
                    mappings={
                        "dynamic": False,
                        "properties": {
                            "name": {"type": "text"},
                            "author": {"type": "text"},
                            "release_date": {"type": "date", "format": "yyyy-MM-dd"},
                            "page_count": {"type": "integer"},
                        },
                    },
                )
            await client.bulk(
                operations=[
                    {"index": {"_index": "my-books"}},
                    {
                        "name": "1984",
                        "author": "George Orwell",
                        "release_date": "1985-06-01",
                        "page_count": 328,
                    },
                ],
            )
            resp = await client.search(
                index="my-books",
                query={"match": {"name": "brave"}},
            )
            print(resp)
        finally:
            await es_client_manager.close()

    asyncio.run(test())
