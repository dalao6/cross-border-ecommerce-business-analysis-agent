"""表元数据业务实体。"""

from dataclasses import dataclass


@dataclass
class TableInfo:
    """系统内部统一使用的表元数据表达"""

    id: str
    name: str
    role: str
    description: str
