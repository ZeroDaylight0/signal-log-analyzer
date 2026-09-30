import argparse
import json
import subprocess

import pytest

from loganalyzer.analysis import AnalysisResult
from loganalyzer.cli import _read_service, _run_analysis
from loganalyzer.errors import LogAnalyzerError


def test_service_uses_safe_journalctl_argument_list(monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="service log\n", stderr="")

    monkeypatch.setattr("loganalyzer.cli.subprocess.run", run)
    text = _read_service("unit;not-a-shell-command", "2 hours ago", 50)

    assert text == "service log\n"
    assert "unit;not-a-shell-command" in captured["command"]
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["timeout"] == 30


def test_service_line_limit_is_validated_before_journalctl(monkeypatch):
    monkeypatch.setattr(
        "loganalyzer.cli.subprocess.run",
        lambda *_args, **_kwargs: pytest.fail("journalctl should not be started"),
    )

    with pytest.raises(LogAnalyzerError, match="between 1 and 10000"):
        _read_service("example.service", "1 hour ago", 0)


def test_cli_writes_json_report_to_output(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    source = tmp_path / "app.log"
    source.write_text("one line\n", encoding="utf-8")

    result = AnalysisResult(
        filename="app.log",
        summary="No issues.",
        overall_severity="low",
        incidents=[],
        timeline=[],
        recommendations=["Keep monitoring."],
        caveats=[],
        log_lines=1,
        truncated=False,
    )
    monkeypatch.setattr("loganalyzer.cli.analyze_log", lambda _text, _filename: result)

    args = argparse.Namespace(
        command="analyze",
        file=source,
        format="json",
        output=output,
    )

    assert _run_analysis(args) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"] == "No issues."
    assert payload["recommendations"] == ["Keep monitoring."]
