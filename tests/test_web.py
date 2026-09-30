import asyncio
import json

import httpx

from loganalyzer.analysis import AnalysisResult
from loganalyzer.web import app

SETTINGS = json.dumps(
    {
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "api_key": "test-key",
    }
)


async def _request(method, url, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, url, **kwargs)


def request(method, url, **kwargs):
    return asyncio.run(_request(method, url, **kwargs))


def test_dashboard_and_local_assets_load():
    page = request("GET", "/")
    css = request("GET", "/assets/app.css")
    settings_script = request("GET", "/assets/settings.js")

    assert page.status_code == 200
    assert "Найдите главное" in page.text
    assert css.status_code == 200
    assert "drop-zone" in css.text
    assert settings_script.status_code == 200
    assert "AES-GCM" in settings_script.text


def test_upload_returns_analysis(monkeypatch):
    result = AnalysisResult(
        filename="app.log",
        summary="A failed connection was observed.",
        overall_severity="medium",
        incidents=[],
        timeline=[],
        recommendations=["Check the database."],
        caveats=[],
        log_lines=1,
        truncated=False,
    )
    captured = {}

    def fake_analyze(text, filename, settings):
        captured["text"] = text
        captured["filename"] = filename
        captured["settings"] = settings
        return result

    monkeypatch.setattr("loganalyzer.web.analyze_log", fake_analyze)

    response = request(
        "POST",
        "/api/analyze",
        data={"settings": SETTINGS},
        files={"file": ("app.log", b"connection refused", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "app.log"
    assert response.json()["recommendations"] == ["Check the database."]
    assert captured["text"] == "connection refused"
    assert captured["filename"] == "app.log"
    assert captured["settings"].provider == "openai"
    assert captured["settings"].api_key == "test-key"
    assert captured["settings"].model == "gpt-4.1-mini"


def test_upload_rejects_file_over_limit():
    response = request(
        "POST",
        "/api/analyze",
        data={"settings": SETTINGS},
        files={"file": ("large.log", b"x" * (1_048_576 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert "1 MB limit" in response.json()["detail"]


def test_invalid_provider_settings_do_not_echo_api_key():
    response = request(
        "POST",
        "/api/analyze",
        data={
            "settings": json.dumps(
                {
                    "provider": "unknown",
                    "model": "model",
                    "api_key": "do-not-echo-this-key",
                }
            )
        },
        files={"file": ("app.log", b"service started", "text/plain")},
    )

    assert response.status_code == 422
    assert "do-not-echo-this-key" not in response.text
