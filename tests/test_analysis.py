import json

import httpx
import pytest

from loganalyzer.analysis import ProviderSettings, _environment_settings, analyze_log, prepare_log
from loganalyzer.errors import ConfigurationError, LogAnalyzerError


def test_prepare_log_keeps_edges_and_marks_truncation():
    prepared = prepare_log("A" * 200, max_chars=100)

    assert prepared.truncated is True
    assert prepared.line_count == 1
    assert len(prepared.text) == 100
    assert prepared.text.startswith("A")
    assert prepared.text.endswith("A")
    assert "omitted" in prepared.text


def test_prepare_log_leaves_short_logs_unchanged():
    prepared = prepare_log("first\nsecond")

    assert prepared.text == "first\nsecond"
    assert prepared.line_count == 2
    assert prepared.truncated is False


def test_prepare_log_respects_tiny_limits():
    prepared = prepare_log("log contents", max_chars=4)

    assert len(prepared.text) == 4
    assert prepared.truncated is True


def test_analyze_log_uses_system_instruction_and_validates_result(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    captured = {}
    body = {
        "summary": "One failed database connection.",
        "overall_severity": "medium",
        "incidents": [
            {
                "title": "Database unavailable",
                "severity": "medium",
                "confidence": "high",
                "evidence": [{"line": 1, "text": "connection refused"}],
                "explanation": "The database refused the connection.",
            }
        ],
        "timeline": [],
        "recommendations": ["Check database health."],
        "caveats": [],
    }

    def responder(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(body)}]}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        result = analyze_log("connection refused", r"C:\logs\app.log", client=client)

    assert result.filename == "app.log"
    assert result.log_lines == 1
    assert result.incidents[0].evidence[0].line == 1
    assert captured["request"].headers["x-goog-api-key"] == "test-key"
    assert captured["payload"]["system_instruction"]["parts"][0]["text"].startswith(
        "You are a senior site reliability engineer"
    )
    assert "connection refused" in captured["payload"]["contents"][0]["parts"][0]["text"]
    assert "connection refused" not in captured["payload"]["system_instruction"]["parts"][0]["text"]


@pytest.mark.parametrize(
    ("provider", "model", "base_url", "expected_url", "expected_header"),
    [
        ("openai", "gpt-4.1-mini", None, "https://api.openai.com/v1/chat/completions", "Authorization"),
        ("anthropic", "claude-3-5-haiku-latest", None, "https://api.anthropic.com/v1/messages", "x-api-key"),
        ("xai", "grok-3-mini-fast", None, "https://api.x.ai/v1/chat/completions", "Authorization"),
        ("openai-compatible", "local/model", "http://localhost:1234/v1", "http://localhost:1234/v1/chat/completions", "Authorization"),
    ],
)
def test_provider_adapters_normalize_responses(
    provider, model, base_url, expected_url, expected_header
):
    settings = ProviderSettings(
        provider=provider,
        model=model,
        api_key="provider-test-key",
        base_url=base_url,
    )
    analysis = {
        "summary": "Сбой соединения.",
        "overall_severity": "medium",
        "incidents": [],
        "timeline": [],
        "recommendations": ["Проверить сервис."],
        "caveats": [],
    }
    captured = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        text = json.dumps(analysis)
        if provider == "anthropic":
            response = {"content": [{"type": "text", "text": text}]}
        else:
            response = {"choices": [{"message": {"content": text}}]}
        return httpx.Response(200, json=response)

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        result = analyze_log("connection refused", "app.log", settings=settings, client=client)

    assert result.summary == "Сбой соединения."
    assert captured["url"] == expected_url
    assert captured["headers"][expected_header] in {"Bearer provider-test-key", "provider-test-key"}
    if provider == "anthropic":
        assert captured["headers"]["anthropic-version"] == "2023-06-01"
        assert "senior site reliability engineer" in captured["body"]["system"]
    else:
        assert captured["body"]["messages"][0]["role"] == "system"
    if provider == "openai-compatible":
        assert captured["body"]["model"] == "local/model"


def test_gemini_provider_uses_explicit_settings_without_environment(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = ProviderSettings(provider="gemini", model="gemini-2.5-flash", api_key="browser-key")
    result_body = {
        "summary": "Сервис работает.",
        "overall_severity": "info",
        "incidents": [],
        "timeline": [],
        "recommendations": [],
        "caveats": [],
    }

    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(result_body)}]}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        result = analyze_log("service ready", settings=settings, client=client)

    assert result.overall_severity == "info"


def test_compatible_provider_rejects_invalid_base_url():
    with pytest.raises(ValueError, match="valid HTTP"):
        ProviderSettings(
            provider="openai-compatible",
            model="model",
            api_key="secret",
            base_url="javascript:alert(1)",
        )


def test_compatible_provider_requires_https_for_remote_api():
    with pytest.raises(ValueError, match="Use HTTPS"):
        ProviderSettings(
            provider="openai-compatible",
            model="model",
            api_key="secret",
            base_url="http://api.example.com/v1",
        )


def test_compatible_provider_allows_local_http_api():
    settings = ProviderSettings(
        provider="openai-compatible",
        model="model",
        api_key="secret",
        base_url="http://127.0.0.1:1234/v1",
    )

    assert settings.base_url == "http://127.0.0.1:1234/v1"


def test_cli_environment_supports_non_gemini_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "environment-test-key")
    monkeypatch.setenv("AI_MODEL", "gpt-4.1-mini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    settings = _environment_settings()

    assert settings.provider == "openai"
    assert settings.api_key == "environment-test-key"
    assert settings.model == "gpt-4.1-mini"


def test_analyze_log_fails_clearly_without_api_key(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="AI_API_KEY is not set"):
        analyze_log("some log line")


def test_analyze_log_rejects_empty_input(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with pytest.raises(LogAnalyzerError, match="empty"):
        analyze_log(" \n ")


def test_analyze_log_reports_upstream_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        with pytest.raises(LogAnalyzerError, match="HTTP 429: quota exceeded"):
            analyze_log("error", client=client)
