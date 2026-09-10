"""应用配置。

集中管理数据库路径、分析基准日期、外部搜索后端、LLM（可选）与审计日志等配置。
所有配置都提供合理默认值，保证在没有外部依赖时也能直接运行离线演示。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录（backend 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    """应用运行配置。"""

    # ---- 数据库 ----
    db_path: str = str(DATA_DIR / "yiyi.db")

    # ---- 分析基准日期 ----
    # 演示数据覆盖 2024-01 ~ 2025-12，"今天"固定为 2025-12-31，
    # 使「今年」「最近30天」「同比」等相对时间语义与验收案例一致。
    today: str = "2025-12-31"

    # ---- 外部搜索 ----
    # mock：使用内置的可信外部信息知识库（离线可用）
    # real：调用真实搜索 API（需自行实现 backend/tools/external_web_search.py 中的后端）
    external_search_backend: str = field(default_factory=lambda: os.getenv("EXTERNAL_SEARCH_BACKEND", "mock"))

    # ---- 阿里云 OpenSearch（商品搜索）----
    # 申请：阿里云 → 开放搜索 OpenSearch → 创建「文档搜索」类型应用
    # 文档：https://help.aliyun.com/zh/open-search/
    aliyun_access_key_id: str = field(default_factory=lambda: os.getenv("ALIYUN_ACCESS_KEY_ID", ""))
    aliyun_access_key_secret: str = field(default_factory=lambda: os.getenv("ALIYUN_ACCESS_KEY_SECRET", ""))
    aliyun_opensearch_endpoint: str = field(default_factory=lambda: os.getenv("ALIYUN_OPENSEARCH_ENDPOINT", ""))
    # 必填：已创建的 OpenSearch 应用名（控制台可见）
    aliyun_opensearch_app: str = field(default_factory=lambda: os.getenv("ALIYUN_OPENSEARCH_APP", ""))

    # 商品搜索后端
    # mock：使用内置的 Amazon / Temu / eBay 模拟热销榜（离线可用）
    # aliyun_opensearch：调用阿里云 OpenSearch API
    marketplace_search_backend: str = field(
        default_factory=lambda: os.getenv("MARKETPLACE_SEARCH_BACKEND", "mock")
    )

    # ---- 商品详情抓取 ----
    # 直连 Amazon / Temu / eBay 通常会被反爬拦截；
    # 真实环境推荐对接 ScraperAPI / Bright Data / 阿里云 ScrapingHub 等代理抓取服务。
    # mock：返回内置真实感模拟数据；scraperapi：调用 ScraperAPI；
    # direct：直接 httpx 抓取（仅在受信任网络对小站点有效）。
    product_fetch_backend: str = field(
        default_factory=lambda: os.getenv("PRODUCT_FETCH_BACKEND", "mock")
    )
    scraper_api_key: str = field(default_factory=lambda: os.getenv("SCRAPER_API_KEY", ""))
    # 单次抓取超时（秒）
    fetch_timeout: int = int(os.getenv("FETCH_TIMEOUT", "25"))

    # ---- LLM（可选）----
    # 不设置时，Agent 使用内置的确定性规划器（规则回退），全程离线可跑。
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "Pro/zai-org/GLM-5.1"))

    # ---- 元数据基础设施（MySQL + Qdrant + ES + Embedding）----
    # 与 shopkeeper-agent 对齐：meta 库保存结构化元数据，dw 库为 MySQL 数仓镜像。
    # 离线环境（未启动 Docker）下召回会自动回退到 scoring.py 关键词打分方案。
    mysql_meta_host: str = field(default_factory=lambda: os.getenv("MYSQL_META_HOST", "localhost"))
    mysql_meta_port: int = int(os.getenv("MYSQL_META_PORT", "3306"))
    mysql_meta_user: str = field(default_factory=lambda: os.getenv("MYSQL_META_USER", "didilili"))
    mysql_meta_password: str = field(default_factory=lambda: os.getenv("MYSQL_META_PASSWORD", "dili123"))
    mysql_meta_database: str = field(default_factory=lambda: os.getenv("MYSQL_META_DATABASE", "meta"))

    mysql_dw_host: str = field(default_factory=lambda: os.getenv("MYSQL_DW_HOST", "localhost"))
    mysql_dw_port: int = int(os.getenv("MYSQL_DW_PORT", "3306"))
    mysql_dw_user: str = field(default_factory=lambda: os.getenv("MYSQL_DW_USER", "didilili"))
    mysql_dw_password: str = field(default_factory=lambda: os.getenv("MYSQL_DW_PASSWORD", "dili123"))
    mysql_dw_database: str = field(default_factory=lambda: os.getenv("MYSQL_DW_DATABASE", "dw"))

    qdrant_host: str = field(default_factory=lambda: os.getenv("QDRANT_HOST", "127.0.0.1"))
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_embedding_size: int = int(os.getenv("QDRANT_EMBEDDING_SIZE", "1024"))

    embedding_host: str = field(default_factory=lambda: os.getenv("EMBEDDING_HOST", "127.0.0.1"))
    embedding_port: int = int(os.getenv("EMBEDDING_PORT", "8081"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"))

    es_host: str = field(default_factory=lambda: os.getenv("ES_HOST", "127.0.0.1"))
    es_port: int = int(os.getenv("ES_PORT", "9200"))
    es_index_name: str = field(default_factory=lambda: os.getenv("ES_INDEX_NAME", "data_agent"))

    # ---- 召回后端 ----
    # auto：运行时检测 Qdrant/ES/Embedding 是否可用，不可用自动回退 scoring；
    # on：强制向量召回（基础设施不可用时召回会返回空）；
    # off：强制关键词打分（完全离线）。
    vector_recall_backend: str = field(default_factory=lambda: os.getenv("VECTOR_RECALL_BACKEND", "auto"))

    # ---- Human-in-the-Loop 人工审核 ----
    # auto：高风险操作自动放行（离线演示默认，6 个验收案例可跑通）
    # manual：高风险操作（执行 SQL / 跨境平台搜索）前暂停，等待人工确认（经 /api/query/confirm 恢复）
    hitl_mode: str = field(default_factory=lambda: os.getenv("HITL_MODE", "auto"))

    # ---- 审计日志 ----
    audit_log_path: str = str(DATA_DIR / "audit.log")

    # ---- 服务 ----
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def use_llm(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def use_aliyun_opensearch(self) -> bool:
        """是否启用真实的阿里云 OpenSearch 后端。"""
        return bool(
            self.aliyun_access_key_id
            and self.aliyun_access_key_secret
            and self.aliyun_opensearch_endpoint
            and self.aliyun_opensearch_app
        )

    @property
    def use_scraper_api(self) -> bool:
        """是否启用 ScraperAPI 抓取后端。"""
        return self.product_fetch_backend == "scraperapi" and bool(self.scraper_api_key)


settings = Settings()