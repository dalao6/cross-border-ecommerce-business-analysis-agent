"""
字段取值 ES 仓储

把字段真实取值组织成 Elasticsearch 全文索引，并提供索引创建、批量写入和关键词检索能力。
Service 层负责决定哪些字段需要同步，Repository 只关心索引是否存在、ValueInfo 如何写进 ES 以及如何按关键词召回。

本文件从 shopkeeper-agent 对齐移植而来，包名由 app 改为 backend。
"""

from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from backend.entities.value_info import ValueInfo


class ValueESRepository:
    """负责字段取值全文索引的创建、写入和基础检索"""

    index_name = "value_index"
    index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_max_word",
            },
            "column_id": {"type": "keyword"},
        },
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """确保字段取值索引已经创建好"""
        if not await self.client.indices.exists(index=self.index_name):
            await self.client.indices.create(
                index=self.index_name, mappings=self.index_mappings
            )

    async def index(self, value_infos: list[ValueInfo], batch_size=20):
        """分批写入字段取值，避免一次 bulk 过大"""
        if not value_infos:
            return

        for i in range(0, len(value_infos), batch_size):
            batch_value_infos = value_infos[i : i + batch_size]
            batch_operations = []
            for value_info in batch_value_infos:
                batch_operations.append(
                    {"index": {"_index": self.index_name, "_id": value_info.id}}
                )
                batch_operations.append(asdict(value_info))
            await self.client.bulk(operations=batch_operations)

    async def search(
        self, keyword: str, score_threshold: float = 0.6, limit: int = 20
    ) -> list[ValueInfo]:
        """按关键词全文检索字段取值，并还原为 ValueInfo 实体"""
        resp = await self.client.search(
            index=self.index_name,
            query={"match": {"value": keyword}},
            size=limit,
            min_score=score_threshold,
        )
        return [ValueInfo(**hit["_source"]) for hit in resp["hits"]["hits"]]
