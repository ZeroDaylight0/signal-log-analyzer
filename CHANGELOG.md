# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Editor config, security policy and contributing guide.
- Likely secrets are masked locally before a log is sent to a provider; the
  report says how many values were masked.

### Security
- The web server rejects cross-site POST requests, so other websites cannot
  trigger analyses or calls to local `openai-compatible` endpoints.

## [0.1.0]

### Added
- Log analysis for local files and Linux services.
- CLI entry point `loganalyzer`.
- Local web dashboard (FastAPI) with settings page.
- Support for multiple AI providers.
