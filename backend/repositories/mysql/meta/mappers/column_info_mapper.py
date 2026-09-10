"""ColumnInfo 映射器：在字段元数据业务实体和 ORM 模型之间做双向转换。"""

from dataclasses import asdict

from backend.entities.column_info import ColumnInfo
from backend.models.column_info import ColumnInfoMySQL


class ColumnInfoMapper:
    """负责 `ColumnInfo` 与 `ColumnInfoMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(column_info_mysql: ColumnInfoMySQL) -> ColumnInfo:
        return ColumnInfo(
            id=column_info_mysql.id,
            name=column_info_mysql.name,
            type=column_info_mysql.type,
            role=column_info_mysql.role,
            examples=column_info_mysql.examples,
            description=column_info_mysql.description,
            alias=column_info_mysql.alias,
            table_id=column_info_mysql.table_id,
        )

    @staticmethod
    def to_model(column_info: ColumnInfo) -> ColumnInfoMySQL:
        return ColumnInfoMySQL(**asdict(column_info))
