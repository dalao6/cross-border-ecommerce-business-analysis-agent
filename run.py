"""启动脚本：python run.py 即可启动服务。"""

import sys

from dotenv import load_dotenv

load_dotenv()

import uvicorn

from backend.config import settings


def kill_port_process(port: int) -> None:
    if sys.platform != "win32":
        return
    import subprocess

    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = int(parts[-1])
                if pid and pid != 0:
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                   capture_output=True, timeout=5)
                    print(f"已自动终止占用端口 {port} 的旧进程 (PID={pid})")
    except Exception:
        pass


if __name__ == "__main__":
    kill_port_process(settings.port)
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )