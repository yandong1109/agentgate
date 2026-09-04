from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any

LOGGING_ENABLED = True


def _log(message: str) -> None:
    if LOGGING_ENABLED:
        print(f"[agent-test-task] {message}")


def _health_check(url: str, timeout_seconds: float = 3) -> bool:
    try:
        proc = subprocess.run(
            ["curl", "-fsS", "--max-time", str(timeout_seconds), url],
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 1,
        )
        if proc.returncode != 0:
            return False
        payload = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok"


def _wait_for_health(service_name: str, health_url: str, timeout_seconds: float = 30) -> bool:
    _log(f"waiting for {service_name} health check")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _health_check(health_url):
            _log(f"{service_name} health check passed")
            return True
        time.sleep(1)
    _log(f"{service_name} health check failed: timeout after {timeout_seconds:g}s")
    return False


def _is_tcp_port_open(host: str, port: int, timeout_seconds: float = 1) -> bool:
    try:
        proc = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and f"{host}:{port} (LISTEN)" in proc.stdout


@dataclass
class Target:
    type: str
    id: str
    version_id: str


@dataclass
class query_trace:
    base_url: str = "http://127.0.0.1:8030"
    output_dir: str = "."

    def get_trace(self, trace_id: str) -> bool:
        url = f"{self.base_url}/api/v1/projects/all/traces/{trace_id}"
        output_file = os.path.join(self.output_dir, f"trace-{trace_id}.json")
        _log(f"query_trace trace_id={trace_id}")
        proc = subprocess.run(
            ["curl", "-sS", url, "-o", output_file],
            capture_output=True,
            text=True,
        )
        _log(f"query_trace done returncode={proc.returncode} output={output_file}")
        return proc.returncode == 0


@dataclass
class AgentExecutePerInvocation_id:
    invocation_id: str
    idempotency_key: str
    target: Target
    run_id: str
    case_id: str
    turn_id: str
    input: Any
    state: dict[str, Any] = field(default_factory=dict)

    def print_1(self) -> None:
        _log("print_1")
        print("print-1")

    def print_2(self) -> None:
        _log("print_2")
        print("print-2")

    def agent_executor(
        self,
        target: Target,
        input: Any,
        state: dict[str, Any],
        timeout_seconds: float,
        invocation_id: str | None = None,
        traceparent: str | None = None,
        baggage: str | None = None,
    ) -> dict[str, Any]:
        _log("agent_executor")
        pass

    def start_agent_http_listening(self, host: str = "127.0.0.1", port: int = 8123) -> bool:
        _log(f"start_agent_http_listening host={host} port={port}")
        health_url = f"http://{host}:{port}/health"
        if _health_check(health_url):
            _log("agent http server already healthy, reusing it")
            return True
        if _is_tcp_port_open(host, port):
            _log("agent http server port is already in use, but health check failed")
            return False

        env = os.environ.copy()
        env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
        _log("starting agent http server process")
        subprocess.Popen(
            [".venv/bin/python", "-m", "dialog_agent.http_server", "--host", host, "--port", str(port)],
            cwd="/Users/baibo/01-XunZhan/0830-codex",
            env=env,
        )
        if not _wait_for_health("agent http server", health_url):
            return False
        _log("agent http server started")
        return True

    def execute_agent_http(
        self,
        target: Target,
        input: Any,
        state: dict[str, Any],
        timeout_seconds: float | None = None,
        invocation_id: str | None = None,
        traceparent: str | None = None,
        baggage: str | None = None,
        base_url: str = "http://127.0.0.1:8123",
    ) -> dict[str, Any]:
        _log("execute_agent_http")
        endpoint = f"{base_url.rstrip('/')}/chat"
        payload = json.dumps(
            {
                "input": input,
                "invocation_id": invocation_id,
                "target": asdict(target),
                "state": state,
            },
            ensure_ascii=False,
        )
        _log("request:")
        _log(f"  curl -sS -X POST '{endpoint}'")
        _log("  -H 'Content-Type: application/json'")
        _log(f"  --data-raw '{payload}'")
        proc = subprocess.run(
            [
                "curl", "-sS", "-X", "POST",
                endpoint,
                "-H", "Content-Type: application/json",
                "--data-raw", payload,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        _log("response:")
        _log(f"  returncode={proc.returncode}")
        _log(f"  stdout={proc.stdout}")
        _log(f"  stderr={proc.stderr}")
        try:
            _log("execute_agent_http done")
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            _log("execute_agent_http response is not valid JSON")
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }

    def start_trace_server(self, host: str = "127.0.0.1", port: int = 8030) -> bool:
        _log(f"start_trace_server host={host} port={port}")
        health_url = f"http://{host}:{port}/health"
        if _health_check(health_url):
            _log("trace server already healthy, reusing it")
            return True
        if _is_tcp_port_open(host, port):
            _log("trace server port is already in use, but health check failed")
            return False

        env = os.environ.copy()
        env["STORAGE_BACKEND"] = "file"
        env["DATA_FILE"] = "/Users/baibo/01-XunZhan/0830-codex/trace_data"
        env["HOST"] = host
        env["PORT"] = str(port)
        _log("starting trace server process")
        subprocess.Popen(
            ["./.venv/bin/python", "backend/scripts/run_api.py"],
            cwd="/Users/baibo/01-XunZhan/trace-sdk/tracev2-master/trace_server",
            env=env,
        )
        _log("start_trace_server started")
        return _wait_for_health("trace server", health_url)


setattr(AgentExecutePerInvocation_id, "agent-executor", AgentExecutePerInvocation_id.agent_executor)
setattr(AgentExecutePerInvocation_id, "Start-agent-http-listening", AgentExecutePerInvocation_id.start_agent_http_listening)
setattr(AgentExecutePerInvocation_id, "Execute-Agent-http", AgentExecutePerInvocation_id.execute_agent_http)
setattr(AgentExecutePerInvocation_id, "Start-trace-server", AgentExecutePerInvocation_id.start_trace_server)


    # task = AgentExecutePerInvocation_id(
    #     invocation_id="invocation-001",
    #     idempotency_key="idempotency-001",
    #     target=Target(
    #         type="agent",
    #         id="agent-test-task",
    #         version_id="v1",
    #     ),
    #     run_id="run-001",
    #     case_id="case-001",
    #     turn_id="turn-001",
    #     input={"message": "请调研苏州市"},
    #     state={},
    # )
    # task.start_agent_http_listening()
    # task.execute_agent_http(
    #     target=task.target,
    #     input=task.input,
    #     state=task.state,
    #     invocation_id=task.invocation_id,
    # )
    # task.start_trace_server()
    # query_trace().get_trace(trace_id=task.invocation_id)