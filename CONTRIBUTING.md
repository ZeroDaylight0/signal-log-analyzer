# Contributing

## Development setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Tests

```bash
pytest -q
```

## Guidelines

- Keep pull requests small and focused.
- New analysis rules or CLI options should come with tests in `tests/`.
- Use anonymized sample logs only — never real production logs with secrets or personal data.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
