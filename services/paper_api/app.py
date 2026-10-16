from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .config import Settings
from .db import connection, initialize, digest, uid, encode, enqueue, event
from .analytics import delete_workspaces
from .sources import arxiv_id, CLASSIC_SOURCES
from .pdf import PaperError


COOKIE = "paper_loop_session"


class Action(BaseModel):
    block_ids: list[str] = Field(default_factory=list, max_length=200)
    question: str = Field(default="", max_length=4000)
    page: int | None = Field(default=None, ge=1, le=100)
    request_id: str = Field(default="", max_length=100)


class Progress(BaseModel):
    page: int = Field(ge=1, le=100)


class Event(BaseModel):
    kind: Literal["claim_view", "hint_view", "feedback_positive", "feedback_negative", "classic_open", "classic_next", "reader_open"]
    workspace: str | None = Field(default=None, max_length=40)
    category: str = Field(default="", max_length=80)


def workspace_for(db, identifier, owner):
    row = db.execute("SELECT * FROM workspaces WHERE id=? AND owner=?", (identifier, owner)).fetchone()
    if not row:
        raise HTTPException(404, "论文不存在、已过期，或不属于当前浏览器。")
    return dict(row)


def consume(db, settings, owner, kind):
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current = db.execute("SELECT amount FROM quota WHERE owner=? AND day=? AND kind=?", (owner, day, kind)).fetchone()
    limit = settings.daily_imports if kind == "import" else settings.daily_actions
    if current and current[0] >= limit:
        raise HTTPException(429, "今日免费次数已用完，已有论文仍可继续阅读。次数在 UTC 零点重置。")
    total = db.execute("SELECT coalesce(sum(amount),0) FROM quota WHERE day=? AND kind=?", (day, kind)).fetchone()[0]
    global_limit = settings.global_actions if kind == "action" else max(1, settings.global_actions // 5)
    if total >= global_limit:
        raise HTTPException(429, "今天的全站处理额度已用完，请明天再试。")
    db.execute("INSERT INTO quota VALUES(?,?,?,1) ON CONFLICT(owner,day,kind) DO UPDATE SET amount=amount+1", (owner, day, kind))


def public_job(row):
    return {key: (json.loads(row[key]) if row[key] else None) if key == "result" else row[key] for key in ("id", "kind", "status", "result", "error", "created")}


def create_app(settings=None):
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        initialize(settings)
        yield
    app = FastAPI(title="Paper Loop API", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings

    @app.middleware("http")
    async def privacy(request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                if int(request.headers.get("content-length", "0")) > settings.max_bytes + 1024 * 1024:
                    return JSONResponse({"detail": "请求超过文件大小限制。"}, 413)
            except ValueError:
                return JSONResponse({"detail": "请求长度无效。"}, 400)
            origin = request.headers.get("origin")
            if (origin and origin not in settings.origins) or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "请求来源不受支持。"}, 403)
        token = request.cookies.get(COOKIE, "")
        new = False
        with connection(settings, True) as db:
            owner = digest(token) if token else ""
            if not owner or not db.execute("SELECT 1 FROM sessions WHERE id=?", (owner,)).fetchone():
                token = secrets.token_urlsafe(32)
                owner = digest(token)
                db.execute("INSERT INTO sessions VALUES(?,?)", (owner, time.time()))
                new = True
            # Minute buckets contain no IPs or request bodies and expire in cleanup.
            minute = str(int(time.time() // 60))
            rate = db.execute("SELECT amount FROM quota WHERE owner=? AND day=? AND kind='rate'", (owner, minute)).fetchone()
            if rate and rate[0] >= 180:
                return JSONResponse({"detail": "操作过于频繁，请稍后重试。"}, 429)
            db.execute("INSERT INTO quota VALUES(?,?,'rate',1) ON CONFLICT(owner,day,kind) DO UPDATE SET amount=amount+1", (owner, minute))
        request.state.owner = owner
        response = await call_next(request)
        if new:
            response.set_cookie(COOKIE, token, max_age=180 * 86400, httponly=True, secure=settings.secure_cookie, samesite="lax", path="/")
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/session")
    def session(request: Request):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with connection(settings, True) as db:
            quota = {r["kind"]: r["amount"] for r in db.execute("SELECT kind,amount FROM quota WHERE owner=? AND day=?", (request.state.owner, day))}
            visited = db.execute("SELECT 1 FROM events WHERE owner=? AND kind='visit' AND date(created,'unixepoch')=?", (request.state.owner, day)).fetchone()
            if not visited:
                event(db, request.state.owner, None, "visit")
        return {"ai_available": bool(settings.api_key), "retention_days": settings.retention_days, "remaining_imports": max(0, settings.daily_imports - quota.get("import", 0)), "remaining_actions": max(0, settings.daily_actions - quota.get("action", 0))}

    @app.post("/api/imports")
    async def import_paper(request: Request, file: UploadFile | None = File(default=None), arxiv: str = Form(default=""), classic: str = Form(default=""), consent: bool = Form(default=False)):
        if not consent:
            raise HTTPException(400, "请先确认数据保存与需求分析说明。")
        if sum([bool(file), bool(arxiv.strip()), bool(classic)]) != 1:
            raise HTTPException(400, "请选择 PDF 或填写 arXiv 地址，二选一。")
        identifier, temp, source_key = None, None, ""
        if file:
            temp = settings.data_dir / "files" / (uid() + ".upload")
            size, sha = 0, hashlib.sha256()
            try:
                with temp.open("wb") as output:
                    while chunk := await file.read(65536):
                        size += len(chunk)
                        if size > settings.max_bytes:
                            raise HTTPException(413, "PDF 超过 30 MB 限制。")
                        sha.update(chunk)
                        output.write(chunk)
                with temp.open("rb") as source:
                    if not source.read(1024).lstrip().startswith(b"%PDF-"):
                        raise HTTPException(400, "请选择有效的 PDF 文件。")
                source_key = "sha256:" + sha.hexdigest()
            except Exception:
                temp.unlink(missing_ok=True)
                raise
            finally:
                await file.close()
        elif classic:
            if classic not in CLASSIC_SOURCES:
                raise HTTPException(400, "未知的经典论文来源。")
            source_key = "classic:" + classic
        else:
            try:
                identifier = arxiv_id(arxiv)
            except PaperError as exc:
                raise HTTPException(400, str(exc)) from exc
            source_key = "arxiv:" + identifier
        try:
            with connection(settings, True) as db:
                existing = db.execute("SELECT id,status FROM workspaces WHERE owner=? AND source_key=?", (request.state.owner, source_key)).fetchone()
                if existing:
                    return {"workspace_id": existing["id"], "existing": True}
                consume(db, settings, request.state.owner, "import")
                workspace = uid()
                title = Path(file.filename or "论文.pdf").name if file else ("arXiv · " + identifier if identifier else "经典论文 · " + classic)
                filename = workspace + ".pdf" if file else None
                db.execute("INSERT INTO workspaces(id,owner,title,source_key,source,filename,created) VALUES(?,?,?,?,?,?,?)", (workspace, request.state.owner, title[:220], source_key, "upload" if file else "classic" if classic else "arxiv", filename, time.time()))
                if temp:
                    temp.replace(settings.data_dir / "files" / filename)
                job = enqueue(db, workspace, "import", {"arxiv_id": identifier, "classic": classic}, "import")
                event(db, request.state.owner, workspace, "import_started", "upload" if file else "arxiv")
            return {"workspace_id": workspace, "job_id": job, "existing": False}
        finally:
            if temp:
                temp.unlink(missing_ok=True)

    @app.get("/api/history")
    def history(request: Request):
        with connection(settings) as db:
            rows = db.execute("SELECT id,title,status,error,created,page,json_array_length(pages) page_count,source FROM workspaces WHERE owner=? ORDER BY created DESC", (request.state.owner,)).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.delete("/api/history")
    def clear_history(request: Request):
        with connection(settings, True) as db:
            count = delete_workspaces(db, settings, owner=request.state.owner)
            db.execute("DELETE FROM events WHERE owner=?", (request.state.owner,))
        return {"deleted": count}

    @app.get("/api/workspaces/{identifier}")
    def get_workspace(identifier: str, request: Request):
        with connection(settings) as db:
            row = workspace_for(db, identifier, request.state.owner)
            jobs = [public_job(r) for r in db.execute("SELECT * FROM jobs WHERE workspace=? ORDER BY created", (identifier,))]
            messages = [{**dict(r), "citations": json.loads(r["citations"])} for r in db.execute("SELECT id,role,content,citations,created,job FROM messages WHERE workspace=? ORDER BY created,id", (identifier,))]
        return {**{k: row[k] for k in ("id", "title", "status", "error", "analysis_error", "source", "created", "page")}, "pages": json.loads(row["pages"]), "blocks": json.loads(row["blocks"]), "overview": json.loads(row["overview"]) if row["overview"] else None, "jobs": jobs, "messages": messages, "pdf_available": bool(row["filename"])}

    @app.get("/api/workspaces/{identifier}/pdf")
    def pdf(identifier: str, request: Request):
        with connection(settings) as db:
            row = workspace_for(db, identifier, request.state.owner)
        path = settings.data_dir / "files" / f"{identifier}.pdf"
        if not row["filename"] or not path.is_file():
            raise HTTPException(404, "PDF 尚未准备好。")
        return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=paper.pdf"})

    @app.delete("/api/workspaces/{identifier}")
    def delete_workspace(identifier: str, request: Request):
        with connection(settings, True) as db:
            workspace_for(db, identifier, request.state.owner)
            delete_workspaces(db, settings, owner=request.state.owner, workspace=identifier)
        return {"deleted": True}

    @app.patch("/api/workspaces/{identifier}/progress")
    def progress(identifier: str, value: Progress, request: Request):
        with connection(settings, True) as db:
            row = workspace_for(db, identifier, request.state.owner)
            if value.page > len(json.loads(row["pages"])):
                raise HTTPException(400, "页码超出范围。")
            db.execute("UPDATE workspaces SET page=? WHERE id=?", (value.page, identifier))
            event(db, request.state.owner, identifier, "read_page", str(value.page))
        return {"page": value.page}

    @app.post("/api/workspaces/{identifier}/actions/{kind}")
    def action(identifier: str, kind: Literal["analyze", "translate", "chat", "explain", "retry-import"], value: Action, request: Request):
        with connection(settings, True) as db:
            row = workspace_for(db, identifier, request.state.owner)
            if kind == "retry-import":
                if row["status"] != "failed":
                    raise HTTPException(409, "当前导入无需重试。")
                job = enqueue(db, identifier, "import", {}, "import")
                db.execute("UPDATE workspaces SET status='queued',error=NULL WHERE id=?", (identifier,))
                return {"job_id": job}
            if row["status"] != "ready":
                raise HTTPException(409, "请等待论文解析完成。")
            if not settings.api_key:
                raise HTTPException(503, "AI 服务尚未配置。你可以继续阅读原文，配置模型后重试。")
            blocks = json.loads(row["blocks"])
            valid = {b["id"] for b in blocks}
            chosen = value.block_ids
            if value.page and kind == "translate":
                chosen = [b["id"] for b in blocks if b["page"] == value.page]
            if not set(chosen).issubset(valid):
                raise HTTPException(400, "原文段落不属于当前论文。")
            if kind in {"translate", "explain"} and not chosen:
                raise HTTPException(400, "请先选择有正文的页面或段落。")
            if kind in {"chat", "explain"} and not value.question.strip():
                raise HTTPException(400, "请输入问题。")
            key = "analyze" if kind == "analyze" else "translate:" + digest(encode(chosen)) if kind == "translate" else kind + ":" + (value.request_id or uid())
            existing = db.execute("SELECT * FROM jobs WHERE workspace=? AND cache_key=?", (identifier, key)).fetchone()
            if existing and existing["status"] != "failed":
                return {"job_id": existing["id"]}
            pending = db.execute("SELECT count(*) FROM jobs WHERE workspace=? AND status IN ('queued','running')", (identifier,)).fetchone()[0]
            if pending >= 3:
                raise HTTPException(429, "当前论文已有多个处理任务，请稍候。")
            consume(db, settings, request.state.owner, "action")
            job = enqueue(db, identifier, kind, {"block_ids": chosen, "question": value.question}, key)
            if kind in {"chat", "explain"} and not existing:
                db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?)", (uid(), identifier, "user", value.question, encode(chosen), time.time(), job))
            event(db, request.state.owner, identifier, kind + "_requested")
        return {"job_id": job}

    @app.get("/api/jobs/{identifier}")
    def get_job(identifier: str, request: Request):
        with connection(settings) as db:
            row = db.execute("SELECT jobs.* FROM jobs JOIN workspaces ON workspaces.id=jobs.workspace WHERE jobs.id=? AND workspaces.owner=?", (identifier, request.state.owner)).fetchone()
            if not row:
                raise HTTPException(404, "任务不存在。")
            return public_job(row)

    @app.post("/api/jobs/{identifier}/retry")
    def retry_job(identifier: str, request: Request):
        with connection(settings, True) as db:
            row = db.execute("SELECT jobs.*,workspaces.owner FROM jobs JOIN workspaces ON workspaces.id=jobs.workspace WHERE jobs.id=? AND workspaces.owner=?", (identifier, request.state.owner)).fetchone()
            if not row:
                raise HTTPException(404, "任务不存在。")
            if row["status"] != "failed":
                return {"job_id": identifier}
            if row["kind"] != "import" and not settings.api_key:
                raise HTTPException(503, "AI 服务尚未配置。")
            pending = db.execute("SELECT count(*) FROM jobs WHERE workspace=? AND status IN ('queued','running')", (row["workspace"],)).fetchone()[0]
            if pending >= 3:
                raise HTTPException(429, "请等待当前任务完成。")
            consume(db, settings, request.state.owner, "import" if row["kind"] == "import" else "action")
            db.execute("UPDATE jobs SET status='queued',error=NULL,lease=NULL,claim=NULL WHERE id=?", (identifier,))
            if row["kind"] == "import":
                db.execute("UPDATE workspaces SET status='queued',error=NULL WHERE id=?", (row["workspace"],))
        return {"job_id": identifier}

    @app.post("/api/events")
    def record_event(value: Event, request: Request):
        with connection(settings, True) as db:
            if value.workspace:
                workspace_for(db, value.workspace, request.state.owner)
            # Only bounded categories enter analytics; never arbitrary text or user questions.
            category = value.category if value.category in {"问题定义", "关键方法", "实验结果", "局限", "机制", "公式", "实验", "实现", "背景", "比较", "其他"} else ""
            event(db, request.state.owner, value.workspace, value.kind, category)
        return {"recorded": True}

    return app


app = create_app()
