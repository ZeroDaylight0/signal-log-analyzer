import pytest

from loganalyzer.redaction import MASK, redact_secrets


@pytest.mark.parametrize(
    ("line", "secret"),
    [
        ("login ok password=hunter2 user=bob", "hunter2"),
        ('{"api_key": "abc123def456", "level": "info"}', "abc123def456"),
        ("DB_PASSWORD: s3cr3t!", "s3cr3t!"),
        ("Authorization: Bearer eyabc.def-ghi_123456", "eyabc.def-ghi_123456"),
        ("connecting to postgres://app:Pa55word@db:5432/main", "Pa55word"),
        ("key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv", "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv"),
        ("token ghp_" + "a" * 36, "ghp_" + "a" * 36),
        ("aws AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE"),
        ("bot 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw0 started", "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw0"),
    ],
)
def test_masks_common_secrets(line, secret):
    masked, count = redact_secrets(line)
    assert secret not in masked
    assert MASK in masked
    assert count >= 1


def test_keeps_ordinary_log_lines():
    line = "2026-11-11 10:00:01 ERROR worker[42]: connection to 10.0.0.5:5432 refused (token bucket empty)"
    assert redact_secrets(line) == (line, 0)


def test_private_key_block_keeps_line_count():
    log = "start\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nAAAA\n-----END RSA PRIVATE KEY-----\nend"
    masked, count = redact_secrets(log)
    assert "MIIEow" not in masked
    assert masked.count("\n") == log.count("\n")
    assert masked.splitlines()[-1] == "end"
    assert count == 1
