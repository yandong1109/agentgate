"""独立假 Agent 进程（Playwright E2E 第三个 webServer）。

用法：
    python3 -m tests.fake_agent_server --port 18081 [--behavior success]

遥测双模式：
- OTLP 模式（默认）：FakeHttpAgent 向 AgentGate /v1/traces 上报（存量路径）；
- trace-sdk 模式：设置 AGENTGATE_TRACE_SDK_FILE_ROOT 时启用——经桥接
  （contrib/agentgate_bridge.py）写事件 JSONL，AgentGate 由
  AGENTGATE_TRACE_SDK_FILE_ROOT 拉取（新路径，见 trace-sdk-integration-plan）。
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any
from uuid import uuid4

TRACE_SDK_ROOT = os.getenv("AGENTGATE_TRACE_SDK_FILE_ROOT", "").strip()


class BridgeFakeAgent:
    """trace-sdk 桥接模式的假 Agent：行为与 FakeHttpAgent(success) 对齐。"""

    def __init__(self, output_root: str) -> None:
        # 桥接模块自包含（不依赖 agentgate 包内部），随 PYTHONPATH=src 导入
        from agentgate.contrib.agentgate_bridge import AgentGateBridge

        self.bridge = AgentGateBridge(output_root=output_root)

    def handle(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        traceparent = headers.get("traceparent", "")
        trace_id = next(
            (part for part in traceparent.split("-")[1:2] if len(part) == 32),
            uuid4().hex,
        )
        turns = (body.get("input") or {}).get("turns")
        if isinstance(turns, list) and turns:
            turn_id = turns[-1].get("turn_id")
        else:
            turn_id = body.get("turn_id")
        (turn_trace,) = self.bridge.turn_traces(
            {**body, "turn_id": turn_id}, headers,
        )
        turn_trace.start()
        turn_trace.tool("process", {"input": body.get("input")})
        output = {"message": "processed", "status": "approved"}
        final_state = {"approved": True, "status": "approved"}
        turn_trace.finish(output=output, final_state=final_state)
        self.bridge.flush()
        return {
            "invocation_id": body.get("invocation_id", ""),
            "external_execution_id": f"fake-{uuid4().hex[:12]}",
            "output": output,
            "final_state": final_state,
            "trace_id": trace_id,
        }


def _serve_bridge(port: int, behavior: str) -> None:
    """桥接模式的极简 HTTP 服务（避免拉起 FakeHttpAgent 的 OTLP 逻辑）。"""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    agent = BridgeFakeAgent(TRACE_SDK_ROOT)
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_POST(self):
            length = int(self.headers.get("content-length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            headers = {k.lower(): v for k, v in self.headers.items()}
            received.append(body)
            if behavior == "500":
                self.send_response(500)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "500"}')
                return
            response = agent.handle(body, headers)
            payload = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"fake agent (trace-sdk bridge) listening on :{port}/invoke", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentGate E2E 假 Agent")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--behavior", default="success")
    args = parser.parse_args()

    if TRACE_SDK_ROOT:
        _serve_bridge(args.port, args.behavior)
        return

    # OTLP 模式（存量）
    from tests.fake_http_agent import FakeHttpAgent

    repository = None
    database_path = os.getenv("AGENTGATE_DB")
    if database_path:
        from agentgate.storage.sqlite import SQLiteRepository

        repository = SQLiteRepository(database_path)

    agent = FakeHttpAgent(repository=repository, behavior=args.behavior, port=args.port)
    print(f"fake agent (otlp) listening on {agent.endpoint}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
