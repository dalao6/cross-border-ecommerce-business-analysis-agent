"""字段取值业务实体。"""

from dataclasses import dataclass


@dataclass
class ValueInfo:
    """字段具体取值及其所属字段的业务表达"""

    id: str
    value: str
    column_id: str
