"""MetricInfo 映射器：在指标元数据业务实体和 ORM 模型之间做双向转换。"""

from dataclasses import asdict

from backend.entities.metric_info import MetricInfo
from backend.models.metric_info import MetricInfoMySQL


class MetricInfoMapper:
    """负责 `MetricInfo` 与 `MetricInfoMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(model: MetricInfoMySQL) -> MetricInfo:
        return MetricInfo(
            id=model.id,
            name=model.name,
            description=model.description,
            relevant_columns=model.relevant_columns,
            alias=model.alias,
        )

    @staticmethod
    def to_model(entity: MetricInfo) -> MetricInfoMySQL:
        return MetricInfoMySQL(**asdict(entity))
