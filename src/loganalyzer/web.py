from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .analysis import MAX_UPLOAD_BYTES, AnalysisResult, ProviderSettings, analyze_log
from .errors import EmptyLogError, LogAnalyzerError

STATIC_DIR = Path(__file__).parent / "static"
app = FastAPI(title="Log Analyzer", docs_url=None, redoc_url=None)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/assets/{asset_name}", include_in_schema=False)
def asset(asset_name: str) -> FileResponse:
    if asset_name not in {"app.css", "app.js", "settings.js"}:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(STATIC_DIR / asset_name)


@app.post("/api/analyze", response_model=AnalysisResult)
def analyze_upload(
    file: UploadFile = File(...),
    settings_json: str = Form(..., alias="settings"),
) -> AnalysisResult:
    if len(settings_json) > 16_384:
        raise HTTPException(status_code=413, detail="Provider settings are too large.")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    log_text = content.decode("utf-8", errors="replace")
    try:
        settings = ProviderSettings.model_validate_json(settings_json)
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            detail = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_input=False)
            )
        else:
            detail = "Provider settings must be valid JSON."
        raise HTTPException(status_code=422, detail=detail) from exc
    try:
        return analyze_log(log_text, file.filename or "log", settings=settings)
    except LogAnalyzerError as exc:
        if isinstance(exc, EmptyLogError):
            status_code = 400
        else:
            status_code = 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
