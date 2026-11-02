# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | yes       |

## Notes on data handling

loganalyzer is local-first, but logs often contain secrets, IPs and personal data:

- When an AI provider is configured, selected log excerpts are sent to that provider.
  Review your provider's data retention policy before analyzing sensitive logs.
- API keys for providers should be supplied via environment variables or the local
  settings page and must never be committed.
- The web UI is intended to run on `127.0.0.1`. Do not expose it publicly without authentication.

## Reporting a vulnerability

Please do **not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/ZeroDaylight0/signal-log-analyzer/security/advisories/new)
and include steps to reproduce.
