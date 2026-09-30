import argparse
import subprocess
import sys
from pathlib import Path

import uvicorn

from .analysis import MAX_UPLOAD_BYTES, AnalysisResult, analyze_log
from .errors import LogAnalyzerError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loganalyzer",
        description="Analyze log files or Linux systemd service logs with an AI provider.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze", help="Analyze a local log file.")
    analyze.add_argument("file", type=Path)
    analyze.add_argument("--format", choices=("text", "json"), default="text")
    analyze.add_argument("--output", type=Path, help="Write the report to a file.")

    service = commands.add_parser("service", help="Analyze logs for a systemd service.")
    service.add_argument("unit", help="systemd unit name, for example nginx.service")
    service.add_argument("--since", default="1 hour ago", help="journalctl time range.")
    service.add_argument("--lines", type=int, default=1000, help="Maximum lines (1-10000).")
    service.add_argument("--format", choices=("text", "json"), default="text")
    service.add_argument("--output", type=Path, help="Write the report to a file.")

    web = commands.add_parser("web", help="Start the local upload dashboard.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--reload", action="store_true", help=argparse.SUPPRESS)
    return parser


def _format_result(result: AnalysisResult, output_format: str) -> str:
    if output_format == "json":
        return result.model_dump_json(indent=2)

    lines = [
        f"Log Analyzer | {result.filename}",
        f"Severity: {result.overall_severity.upper()}",
        f"Lines reviewed: {result.log_lines}"
        + (" (input was truncated)" if result.truncated else ""),
        "",
        result.summary,
    ]
    if result.incidents:
        lines.extend(("", "INCIDENTS"))
        for incident in result.incidents:
            lines.append(
                f"- [{incident.severity.upper()}] {incident.title} "
                f"(confidence: {incident.confidence})"
            )
            lines.append(f"  {incident.explanation}")
            for evidence in incident.evidence:
                location = f"line {evidence.line}: " if evidence.line else ""
                lines.append(f"  Evidence: {location}{evidence.text}")
    if result.timeline:
        lines.extend(("", "TIMELINE"))
        for event in result.timeline:
            location = f"line {event.line}: " if event.line else ""
            lines.append(f"- {location}{event.event}")
    if result.recommendations:
        lines.extend(("", "RECOMMENDED NEXT STEPS"))
        lines.extend(f"{index}. {item}" for index, item in enumerate(result.recommendations, 1))
    if result.caveats:
        lines.extend(("", "CAVEATS"))
        lines.extend(f"- {item}" for item in result.caveats)
    return "\n".join(lines)


def _read_file(path: Path) -> str:
    try:
        with path.open("rb") as log_file:
            content = log_file.read(MAX_UPLOAD_BYTES + 1)
    except OSError as exc:
        raise LogAnalyzerError(f"Could not read {path}: {exc}") from exc
    if len(content) > MAX_UPLOAD_BYTES:
        raise LogAnalyzerError(
            f"{path} is larger than the {MAX_UPLOAD_BYTES // 1024} KB limit. "
            "Reduce the file or extract a relevant time range first."
        )
    return content.decode("utf-8", errors="replace")


def _read_service(unit: str, since: str, line_count: int) -> str:
    if not 1 <= line_count <= 10_000:
        raise LogAnalyzerError("--lines must be between 1 and 10000.")
    command = [
        "journalctl",
        "--unit",
        unit,
        "--since",
        since,
        "--lines",
        str(line_count),
        "--no-pager",
        "--output",
        "short-iso-precise",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise LogAnalyzerError("journalctl is not available on this system.") from exc
    except subprocess.TimeoutExpired as exc:
        raise LogAnalyzerError("journalctl timed out while reading service logs.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()[:500]
        raise LogAnalyzerError(f"journalctl failed: {detail or 'permission denied or invalid unit'}") from exc
    return completed.stdout


def _run_analysis(args: argparse.Namespace) -> int:
    if args.command == "analyze":
        text = _read_file(args.file)
        filename = args.file.name
    else:
        text = _read_service(args.unit, args.since, args.lines)
        filename = args.unit
    result = analyze_log(text, filename)
    rendered = _format_result(result, args.format)
    if args.output:
        try:
            args.output.write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            raise LogAnalyzerError(f"Could not write {args.output}: {exc}") from exc
    else:
        print(rendered)
    return 0


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.command == "web":
            if not 1 <= args.port <= 65535:
                raise LogAnalyzerError("--port must be between 1 and 65535.")
            uvicorn.run("loganalyzer.web:app", host=args.host, port=args.port, reload=args.reload)
            return 0
        return _run_analysis(args)
    except LogAnalyzerError as exc:
        print(f"loganalyzer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
