import io
import json
import logging
import zipfile
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from doctool import library
from doctool.config import Settings
from doctool.db import Document, Task, TaskFile, Version
from doctool.deps import get_blobs, get_db, get_settings
from doctool.pdfio import InvalidPdf
from doctool.routers.library import read_upload
from doctool.schemas import ProcessBody, TaskCreate, TaskOut, ToolOut
from doctool.storage import BlobStore
from doctool.tools.base import Tool, ToolError, ToolInput, redact, registry, secret_fields

log = logging.getLogger("doctool")
router = APIRouter(prefix="/api/v1", tags=["tasks"])


def get_secrets(request: Request) -> dict[str, dict]:
    """Secret params (passwords) live in memory only, keyed by task id. Never persisted."""
    return request.app.state.secrets


def get_task_or_404(db: Session, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return task


def get_tool_or_404(tool_id: str) -> Tool:
    tool = registry.get(tool_id)
    if not tool:
        raise HTTPException(404, f"unknown tool '{tool_id}'")
    return tool


def validate_params(tool: Tool, params: dict):
    try:
        return tool.Params.model_validate(params)
    except ValidationError as exc:
        raise HTTPException(
            422, detail=json.loads(exc.json(include_url=False, include_context=False))
        ) from exc


@router.get("/tools", response_model=list[ToolOut])
def list_tools():
    return [
        ToolOut(
            id=t.id,
            title=t.title,
            group=t.group,
            description=t.description,
            accepts=t.accepts,
            min_files=t.min_files,
            max_files=t.max_files,
            params_schema=t.Params.model_json_schema(),
        )
        for t in registry.all()
    ]


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(
    body: TaskCreate, db: Session = Depends(get_db), secrets: dict = Depends(get_secrets)
):
    tool = get_tool_or_404(body.tool)
    params = validate_params(tool, body.params)
    task = Task(tool=tool.id, params=redact(params), state="waiting")
    db.add(task)
    db.commit()
    held = {k: body.params[k] for k in secret_fields(tool.Params) if k in body.params}
    if held:
        secrets[task.id] = held
    return task


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db)):
    return get_task_or_404(db, task_id)


@router.post("/tasks/{task_id}/files", response_model=TaskOut, status_code=201)
async def add_task_file(
    task_id: str,
    file: UploadFile | None = File(None),
    version_id: str | None = Form(None),
    db: Session = Depends(get_db),
    blobs: BlobStore = Depends(get_blobs),
    settings: Settings = Depends(get_settings),
):
    task = get_task_or_404(db, task_id)
    if task.state != "waiting":
        raise HTTPException(409, "task is not waiting for files")
    tool = get_tool_or_404(task.tool)
    position = len([f for f in task.files if f.role == "in"])
    if version_id:
        version = db.get(Version, version_id)
        if not version or not blobs.exists(version.sha256):
            raise HTTPException(404, "version not found")
        tf = TaskFile(
            role="in",
            position=position,
            version_id=version.id,
            filename=version.filename,
            sha256=version.sha256,
        )
    elif file is not None:
        data = await read_upload(file, settings)
        try:
            tool.check_input(data)
        except (InvalidPdf, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        tf = TaskFile(
            role="in",
            position=position,
            filename=library.safe_filename(file.filename or "input", "input"),
            sha256=blobs.put(data),
        )
    else:
        raise HTTPException(422, "provide a file or a version_id")
    task.files.append(tf)
    db.commit()
    return task


@router.post("/tasks/{task_id}/process")
def process_task(
    task_id: str,
    body: ProcessBody | None = None,
    debug: bool = Query(False),
    db: Session = Depends(get_db),
    blobs: BlobStore = Depends(get_blobs),
    secrets: dict = Depends(get_secrets),
):
    body = body or ProcessBody()
    task = get_task_or_404(db, task_id)
    if task.state != "waiting":
        raise HTTPException(409, f"task is {task.state}")
    tool = get_tool_or_404(task.tool)
    raw = {k: v for k, v in task.params.items() if k not in secret_fields(tool.Params)}
    raw.update(secrets.get(task.id, {}))
    params = validate_params(tool, raw)
    ins = [f for f in task.files if f.role == "in"]
    if len(ins) < tool.min_files or (tool.max_files is not None and len(ins) > tool.max_files):
        raise HTTPException(
            422, f"{tool.id} needs {tool.min_files}..{tool.max_files or 'n'} files, got {len(ins)}"
        )
    if debug:
        return {
            "task": task.id,
            "tool": tool.id,
            "params": redact(params),
            "files": [f.filename for f in ins],
        }

    inputs = [ToolInput(f.filename, blobs.read(f.sha256), body.passwords.get(f.id)) for f in ins]
    task.state = "processing"
    db.commit()
    try:
        outputs = tool.run(inputs, params)
    except ToolError as exc:
        task.state = "waiting" if exc.retryable else "error"
        task.error = exc.message
        if not exc.retryable:
            task.finished_at = datetime.now(UTC)
            secrets.pop(task.id, None)
        for f in ins:
            f.state = exc.state
        db.commit()
        raise HTTPException(
            400, detail={"type": "ProcessingError", "state": exc.state, "message": exc.message}
        ) from exc
    except Exception as exc:
        log.exception("tool %s crashed", tool.id)
        task.state, task.error = "error", "internal error"
        secrets.pop(task.id, None)
        db.commit()
        raise HTTPException(500, "internal error while processing") from exc

    try:
        _store_outputs(db, blobs, task, ins, outputs, params, body.save_to_library)
    except InvalidPdf as exc:
        db.rollback()
        task = get_task_or_404(db, task_id)
        task.state, task.error = "error", "tool produced an invalid PDF"
        secrets.pop(task.id, None)
        db.commit()
        raise HTTPException(500, "tool produced an invalid PDF") from exc
    secrets.pop(task.id, None)
    task.state = "success"
    task.error = None
    task.finished_at = datetime.now(UTC)
    db.commit()
    return TaskOut.model_validate(task)


def _store_outputs(db, blobs, task, ins, outputs, params, save_to_library):
    history = {**redact(params), "_sources": [f.version_id for f in ins if f.version_id]}
    single_source = ins[0] if len(ins) == 1 and ins[0].version_id else None
    for i, out in enumerate(outputs):
        sha = blobs.put(out.data)
        tf = TaskFile(
            role="out", position=i, filename=library.safe_filename(out.name, "output"), sha256=sha
        )
        is_pdf = out.data.lstrip()[:5] == b"%PDF-"
        if save_to_library and is_pdf:
            if single_source and len(outputs) == 1:
                parent = db.get(Version, single_source.version_id)
                doc = db.get(Document, parent.document_id)
                version = library.add_version(
                    db, blobs, doc, out.data, out.name, parent, task.tool, history
                )
            else:
                doc = Document(name=tf.filename, tags=[])
                db.add(doc)
                db.flush()
                version = library.add_version(
                    db, blobs, doc, out.data, out.name, None, task.tool, history
                )
            tf.version_id = version.id
        task.files.append(tf)
    db.flush()


@router.get("/tasks/{task_id}/download")
def download_task(
    task_id: str, db: Session = Depends(get_db), blobs: BlobStore = Depends(get_blobs)
):
    task = get_task_or_404(db, task_id)
    outs = [f for f in task.files if f.role == "out"]
    if task.state != "success" or not outs:
        raise HTTPException(409, "task has no output yet")
    if len(outs) == 1:
        f = outs[0]
        media = (
            "application/pdf" if f.filename.lower().endswith(".pdf") else "application/octet-stream"
        )
        return Response(
            blobs.read(f.sha256),
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{f.filename}"'},
        )
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in outs:
            name, n = f.filename, 1
            while name in used:
                n += 1
                name = f"{n}_{f.filename}"
            used.add(name)
            zf.writestr(name, blobs.read(f.sha256))
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="output.zip"'},
    )


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    blobs: BlobStore = Depends(get_blobs),
    secrets: dict = Depends(get_secrets),
):
    task = get_task_or_404(db, task_id)
    shas = {f.sha256 for f in task.files}
    db.delete(task)
    db.commit()
    secrets.pop(task_id, None)
    for sha in shas:
        library.gc_blob(db, blobs, sha)
    return Response(status_code=204)
