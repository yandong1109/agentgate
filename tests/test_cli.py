import json

from typer.testing import CliRunner

from agentgate.cli.application import app


def test_cli_runs_demo(tmp_path):
    database = tmp_path / "cli.db"
    result = CliRunner().invoke(app, ["evaluate", "--version", "loan-agent-v2-fixed", "--database", str(database)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["gate"]["outcome"] == "pass"


def test_serve_requires_port():
    result = CliRunner().invoke(app, ["serve"])
    assert result.exit_code != 0


def test_serve_launches_uvicorn_with_required_port_and_defaults(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: calls.append((a, kw)))
    result = CliRunner().invoke(app, ["serve", "--port", "8000"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("agentgate.server.application:app",)
    assert kwargs == {"host": "0.0.0.0", "port": 8000, "reload": True}


def test_serve_passes_custom_host_and_no_reload(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: calls.append((a, kw)))
    result = CliRunner().invoke(app, ["serve", "--port", "9000", "--host", "127.0.0.1", "--no-reload"])
    assert result.exit_code == 0, result.output
    _, kwargs = calls[0]
    assert kwargs == {"host": "127.0.0.1", "port": 9000, "reload": False}
