"""
MySQL 客户端管理器

统一创建和管理项目中的异步 MySQL 客户端。当前项目会同时连接两套 MySQL：
一套是保存结构化元数据的 meta 数据库，一套是模拟教学数仓的 dw 数据库。
模块对外提供可复用的客户端管理器和 session 工厂，方便脚本入口、服务层和仓储层按统一方式访问数据库。

本文件从 shopkeeper-agent 对齐移植而来，包名由 app 改为 backend。
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from backend.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    """管理 MySQL Engine 和 Session 工厂"""

    def __init__(self, config: DBConfig):
        self.engine: AsyncEngine | None = None
        self.session_factory = None
        self.config = config

    def _get_url(self) -> str:
        """拼接 MySQL 异步连接地址（mysql+asyncmy 表示用 asyncmy 作为异步驱动）"""
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"

    def init(self):
        """初始化 Engine 和 Session 工厂"""
        self.engine = create_async_engine(
            self._get_url(), pool_size=10, pool_pre_ping=True
        )
        self.session_factory = async_sessionmaker(
            self.engine, autoflush=True, expire_on_commit=False
        )

    async def close(self):
        """释放连接池资源"""
        if self.engine is not None:
            await self.engine.dispose()


# 一套连元数据库，一套连数仓模拟库
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)
dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)


if __name__ == "__main__":
    dw_mysql_client_manager.init()

    async def test():
        async with dw_mysql_client_manager.session_factory() as session:
            sql = "select * from fact_order limit 10"
            result = await session.execute(text(sql))
            rows = result.mappings().fetchall()
            print(type(rows))
            print(type(rows[0]))
            print(rows[0]["order_id"])

    asyncio.run(test())
