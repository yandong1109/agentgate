"""独立假 Agent 进程（Playwright E2E 第三个 webServer）。

用法：
    python3 -m tests.fake_agent_server --port 18081 [--behavior success]

行为与进程内 FakeHttpAgent 完全一致；当设置了 AGENTGATE_DB 时直接向
同一 SQLite 库回传 OTLP trace（与后端进程共享库文件），使评测全链路
在浏览器 E2E 中真实闭环。见《02-端到端验证方案》§2.2。
"""

from __future__ import annotations

import argparse
import os
import time

from tests.fake_http_agent import FakeHttpAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentGate E2E 假 Agent")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--behavior", default="success")
    args = parser.parse_args()

    repository = None
    database_path = os.getenv("AGENTGATE_DB")
    if database_path:
        from agentgate.storage.sqlite import SQLiteRepository

        repository = SQLiteRepository(database_path)

    agent = FakeHttpAgent(repository=repository, behavior=args.behavior, port=args.port)
    print(f"fake agent listening on {agent.endpoint}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
