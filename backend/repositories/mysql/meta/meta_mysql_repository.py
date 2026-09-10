"""
元数据库 MySQL 仓储

负责接收业务实体并落到 Meta MySQL。Repository 自身只关心"如何写入"，
而"哪些写操作要放在同一笔事务里"由 Service 层统一决定。
问数链路运行时也会从这里读取元数据，用来把召回到的 id 补齐成完整实体。

本文件从 shopkeeper-agent 对齐移植而来，包名由 app 改为 backend。
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entities.column_info import ColumnInfo
from backend.entities.column_metric import ColumnMetric
from backend.entities.metric_info import MetricInfo
from backend.entities.table_info import TableInfo
from backend.models.column_info import ColumnInfoMySQL
from backend.models.table_info import TableInfoMySQL
from backend.repositories.mysql.meta.mappers.column_info_mapper import ColumnInfoMapper
from backend.repositories.mysql.meta.mappers.column_metric_mapper import ColumnMetricMapper
from backend.repositories.mysql.meta.mappers.metric_info_mapper import MetricInfoMapper
from backend.repositories.mysql.meta.mappers.table_info_mapper import TableInfoMapper


class MetaMySQLRepository:
    """负责把元数据业务实体持久化到 Meta MySQL"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def save_table_infos(self, table_infos: list[TableInfo]):
        self.session.add_all(
            [TableInfoMapper.to_model(table_info) for table_info in table_infos]
        )

    def save_column_infos(self, column_infos: list[ColumnInfo]):
        self.session.add_all(
            [ColumnInfoMapper.to_model(column_info) for column_info in column_infos]
        )

    def save_metric_infos(self, metric_infos: list[MetricInfo]):
        self.session.add_all(
            [MetricInfoMapper.to_model(metric_info) for metric_info in metric_infos]
        )

    def save_column_metrics(self, column_metrics: list[ColumnMetric]):
        self.session.add_all(
            [
                ColumnMetricMapper.to_model(column_metric)
                for column_metric in column_metrics
            ]
        )

    async def get_column_info_by_id(self, id: str) -> ColumnInfo | None:
        """按字段 id 查询字段元数据，供召回信息合并阶段补齐字段上下文"""
        column_info: ColumnInfoMySQL | None = await self.session.get(ColumnInfoMySQL, id)
        if column_info:
            return ColumnInfoMapper.to_entity(column_info)
        return None

    async def get_table_info_by_id(self, id: str) -> TableInfo | None:
        """按表 id 查询表元数据，最终组装成提示词里的表结构信息"""
        table_info: TableInfoMySQL | None = await self.session.get(TableInfoMySQL, id)
        if table_info:
            return TableInfoMapper.to_entity(table_info)
        return None

    async def get_key_columns_by_table_id(self, table_id: str) -> list[ColumnInfo]:
        """查询指定表的主外键字段，避免 Join 关键字段被向量召回漏掉"""
        sql = (
            "select * from column_info where table_id = :table_id "
            "and role in ('primary_key','foreign_key')"
        )
        result = await self.session.execute(text(sql), {"table_id": table_id})
        return [ColumnInfo(**dict(row)) for row in result.mappings().fetchall()]
