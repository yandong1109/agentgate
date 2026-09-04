from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from agentgate.control_plane import EvaluationService
from agentgate.domain import TargetRef, TargetType
from agentgate.storage.sqlite import SQLiteRepository

app = typer.Typer(help="AgentGate 演示评估工具", no_args_is_help=True)


def _service(database: Path | None = None) -> EvaluationService:
    return EvaluationService(SQLiteRepository(database or os.getenv("AGENTGATE_DB", "agentgate.db")))


@app.command()
def evaluate(version: str = typer.Option("loan-agent-v2-fixed", help="目标代理版本"),
             database: Path | None = typer.Option(None, help="SQLite 数据库路径")) -> None:
    """运行贷款审批演示数据集。"""
    service = _service(database)
    run = service.launch(version)
    report = service.run_detail(run.id)
    typer.echo(json.dumps({
        "run_id": run.id,
        "status": run.status,
        "gate": report.gate.model_dump(mode="json"),
    }, ensure_ascii=False))


@app.command("runs")
def list_runs(database: Path | None = typer.Option(None, help="SQLite 数据库路径")) -> None:
    for run in _service(database).repository.list_runs():
        typer.echo(f"{run.id}\t{run.snapshot.target.ref.external_version_id}\t{run.status}")


@app.command()
def show(run_id: str, database: Path | None = typer.Option(None, help="SQLite 数据库路径")) -> None:
    report = _service(database).run_detail(run_id)
    if report is None:
        raise typer.BadParameter("run not found")
    typer.echo(json.dumps({
        "run": report.run.model_dump(mode="json"),
        "results": [item.model_dump(mode="json") for item in report.results],
        "metrics": [item.model_dump(mode="json") for item in report.metrics],
        "gate": report.gate.model_dump(mode="json"),
    }, ensure_ascii=False))


@app.command("evaluate-http")
def evaluate_http(
    endpoint: str = typer.Option(..., help="Agent HTTP endpoint URL"),
    target_id: str = typer.Option(..., help="External target ID"),
    version_id: str = typer.Option(..., help="External version ID"),
    credential_ref: str = typer.Option("", help="Credential env var name"),
    platform_id: str = typer.Option("external", help="Platform ID"),
    dataset: str = typer.Option("loan-risk-policy", help="Dataset ID"),
    dataset_version: int = typer.Option(1, help="Dataset version"),
    timeout_seconds: float = typer.Option(30.0, help="HTTP request timeout"),
    database: Path | None = typer.Option(None, help="SQLite database path"),
) -> None:
    """Launch an HTTP target evaluation against a published dataset."""
    service = _service(database)
    run = service.launch_http(
        TargetRef(
            platform_id=platform_id,
            target_type=TargetType.AGENT,
            external_target_id=target_id,
            external_version_id=version_id,
        ),
        endpoint=endpoint,
        credential_ref=credential_ref or None,
        dataset_id=dataset,
        dataset_version=dataset_version,
        timeout_seconds=timeout_seconds,
    )
    report = service.run_detail(run.id)
    typer.echo(json.dumps({
        "run_id": run.id,
        "status": run.status,
        "gate": report.gate.model_dump(mode="json"),
    }, ensure_ascii=False))


@app.command()
def serve(
    port: int = typer.Option(
        ..., "--port", "-p", help="监听端口（必填，1-65535）", min=1, max=65535,
    ),
    host: str = typer.Option("0.0.0.0", "--host", help="监听地址，默认 0.0.0.0"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="代码热重载（开发默认开启）"),
) -> None:
    """启动 API 服务（开发模式默认热重载，端口必填）。"""
    import uvicorn

    uvicorn.run("agentgate.server.application:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
