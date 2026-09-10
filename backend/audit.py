"""审计日志。

记录每次问数的关键链路信息，用于调试、审计、安全与模型优化。
对应 capsule 第二十八节「审计日志」。
"""

import json
import time
import uuid
from pathlib import Path

from backend.config import settings


def log_audit(entry: dict) -> None:
    """追加一条审计记录（JSON Lines）。"""
    record = {
        "audit_id": str(uuid.uuid4()),
        "created_at": int(time.time()),
        **entry,
    }
    path = Path(settings.audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
