"""TableInfo 映射器：在表元数据业务实体和 ORM 模型之间做双向转换。"""

from dataclasses import asdict

from backend.entities.table_info import TableInfo
from backend.models.table_info import TableInfoMySQL


class TableInfoMapper:
    """负责 `TableInfo` 与 `TableInfoMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(table_info_mysql: TableInfoMySQL) -> TableInfo:
        return TableInfo(
            id=table_info_mysql.id,
            name=table_info_mysql.name,
            role=table_info_mysql.role,
            description=table_info_mysql.description,
        )

    @staticmethod
    def to_model(table_info: TableInfo) -> TableInfoMySQL:
        return TableInfoMySQL(**asdict(table_info))
