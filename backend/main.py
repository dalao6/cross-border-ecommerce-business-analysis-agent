"""FastAPI 应用入口。

注册 API 路由，并把前端静态文件挂载到根路径。
启动时确保 SQLite 演示数据存在。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.chat import chat_router
from backend.api.lifespan import lifespan
from backend.config import settings
from backend.database.seed import build_database

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="依伊服饰 AI 跨境电商经营分析智能体",
    description="数据库驱动 + 外部工具增强的企业经营分析 Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(chat_router)

# 启动时确保演示数据存在
if not Path(settings.db_path).exists():
    build_database(settings.db_path)

# 挂载前端（最后挂载，避免遮蔽 /api 与 /docs）
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
