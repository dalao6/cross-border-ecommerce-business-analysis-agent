"""字段元数据业务实体。"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnInfo:
    """系统内部统一使用的字段元数据表达"""

    id: str
    name: str
    type: str
    role: str
    examples: list[Any]
    description: str
    alias: list[str]
    table_id: str
