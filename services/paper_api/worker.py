"""Run with python -m services.paper_api.worker; persistent leases survive restarts."""
import json
import signal
import time
from pathlib import Path
from .config import Settings
from .db import connection, initialize, uid, encode, event
from . import llm
from .pdf import extract, PaperError
from .sources import download_arxiv, download_classic


def claim(settings):
    now = time.time()
    with connection(settings, True) as db:
        row = db.execute("SELECT * FROM jobs WHERE status='queued' OR (status='running' AND lease<?) ORDER BY created LIMIT 1", (now,)).fetchone()
        if not row:
            return None
        token = uid()
        db.execute("UPDATE jobs SET status='running', lease=?, claim=? WHERE id=?", (now + settings.lease_seconds, token, row["id"]))
        return {**dict(row), "claim": token}


def heartbeat(settings, job):
    with connection(settings, True) as db:
        result = db.execute("UPDATE jobs SET lease=? WHERE id=? AND claim=? AND status='running'", (time.time() + settings.lease_seconds, job["id"], job["claim"]))
        if not result.rowcount:
            raise PaperError("任务已删除或已被其他 Worker 接管。")


def execute(settings, job):
    with connection(settings) as db:
        row = db.execute("SELECT * FROM workspaces WHERE id=?", (job["workspace"],)).fetchone()
        if not row:
            return
        workspace = dict(row)
        history = [dict(r) for r in db.execute("SELECT role,content FROM messages WHERE workspace=? ORDER BY created DESC LIMIT 10", (workspace["id"],))][::-1]
    payload = json.loads(job["payload"])
    metrics = {}
    path = settings.data_dir / "files" / f"{workspace['id']}.pdf"
    try:
        if job["kind"] == "import":
            version = None
            if workspace["source"] == "arxiv":
                version = download_arxiv(payload["arxiv_id"], path, settings.max_bytes)
            elif workspace["source"] == "classic":
                version = download_classic(payload["classic"], path, settings.max_bytes)
            heartbeat(settings, job)
            with connection(settings, True) as db:
                db.execute("UPDATE workspaces SET status='parsing' WHERE id=?", (workspace["id"],))
            result = extract(path, settings.max_pages)
            result["version"] = version
        else:
            blocks = json.loads(workspace["blocks"])
            if job["kind"] == "analyze":
                result, metrics = llm.analyze(settings, blocks, lambda: heartbeat(settings, job))
            elif job["kind"] == "translate":
                chosen = [b for b in blocks if b["id"] in payload["block_ids"]]
                translated = []
                for batch in llm.batches(chosen, 12000):
                    heartbeat(settings, job)
                    response, usage = llm.call(settings, '逐段翻译为中文，保持原意和数字，公式无法还原时保留原文。返回 {"translations":[{"id":"原文块id","text":"中文译文"}]}，每个输入块必须对应一条译文。', llm.evidence(batch))
                    values = response.get("translations", [])
                    valid = {b["id"] for b in batch}
                    clean = {v.get("id"): v.get("text") for v in values if isinstance(v, dict) and v.get("id") in valid and isinstance(v.get("text"), str) and v["text"].strip()}
                    if set(clean) != valid:
                        raise llm.ModelError("部分段落没有完整译文，请重试本页。")
                    translated.extend({"id": b["id"], "text": clean[b["id"]]} for b in batch)
                    for key in usage:
                        metrics[key] = metrics.get(key, 0) + usage[key]
                result = {"translations": translated}
            else:
                overview = json.loads(workspace["overview"]) if workspace["overview"] else None
                chosen = llm.retrieve(blocks, payload["question"], payload.get("block_ids", []), overview)
                instruction = '回答用户的问题：' + payload["question"] + '。返回 {"answer":"中文回答，明确区分论文结论和补充背景；检索证据不足时说依据不足", "citations":["原文块id"], "category":"机制/公式/实验/实现/背景/比较/其他"}。'
                response, metrics = llm.call(settings, instruction, llm.evidence(chosen), history)
                refs = llm.citations(response.get("citations"), chosen)
                answer = response.get("answer")
                if not isinstance(answer, str) or not answer.strip():
                    raise llm.ModelError("模型没有返回有效回答，请重试。")
                if not refs:
                    answer = "依据不足：本次回答没有可验证的论文引用。\n\n" + answer
                result = {"answer": answer, "citations": refs, "category": response.get("category", "其他")}
        with connection(settings, True) as db:
            owned = db.execute("SELECT id FROM jobs WHERE id=? AND claim=? AND status='running'", (job["id"], job["claim"])).fetchone()
            if not owned:
                return
            db.execute("UPDATE jobs SET status='completed',result=?,lease=NULL WHERE id=?", (encode(result), job["id"]))
            if job["kind"] == "import":
                # Source key stays owner-scoped; canonical version is stored separately in the result.
                db.execute("UPDATE workspaces SET title=?,status='ready',error=NULL,filename=?,pages=?,blocks=? WHERE id=?", (result["title"], path.name, encode(result["pages"]), encode(result["blocks"]), workspace["id"]))
                if result["version"]:
                    source = result["version"] if result["version"].startswith("https://") else "https://arxiv.org/abs/" + result["version"]
                    db.execute("UPDATE workspaces SET source=? WHERE id=?", (source, workspace["id"]))
                event(db, workspace["owner"], workspace["id"], "import_success")
                if settings.api_key:
                    from .db import enqueue
                    enqueue(db, workspace["id"], "analyze", {}, "analyze")
                else:
                    db.execute("UPDATE workspaces SET analysis_error=? WHERE id=?", ("AI 服务尚未配置，你可以先阅读 PDF 原文。", workspace["id"]))
            elif job["kind"] == "analyze":
                db.execute("UPDATE workspaces SET overview=?,analysis_error=NULL WHERE id=?", (encode(result), workspace["id"]))
            elif job["kind"] in {"chat", "explain"}:
                db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?)", (uid(), workspace["id"], "assistant", result["answer"], encode(result["citations"]), time.time(), job["id"]))
                category = result["category"] if result["category"] in {"机制", "公式", "实验", "实现", "背景", "比较", "其他"} else "其他"
                event(db, workspace["owner"], workspace["id"], "question_answered", category)
            for key, value in metrics.items():
                event(db, workspace["owner"], workspace["id"], "model_" + key, settings.model, value)
    except Exception as exc:
        safe = str(exc) if isinstance(exc, (PaperError, llm.ModelError)) else "任务暂时无法完成，请稍后重试。"
        with connection(settings, True) as db:
            changed = db.execute("UPDATE jobs SET status='failed',error=?,lease=NULL WHERE id=? AND claim=?", (safe, job["id"], job["claim"]))
            if changed.rowcount:
                if job["kind"] == "import":
                    db.execute("UPDATE workspaces SET status='failed',error=? WHERE id=?", (safe, workspace["id"]))
                    event(db, workspace["owner"], workspace["id"], "import_failure")
                elif job["kind"] == "analyze":
                    db.execute("UPDATE workspaces SET analysis_error=? WHERE id=?", (safe, workspace["id"]))
    finally:
        # A deletion during a remote request must not resurrect an orphan PDF.
        with connection(settings) as db:
            exists = db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace["id"],)).fetchone()
        if not exists:
            path.unlink(missing_ok=True)


def run_once(settings):
    job = claim(settings)
    if not job:
        return False
    execute(settings, job)
    return True


def main():
    settings = Settings()
    initialize(settings)
    active = True
    def stop(*_):
        nonlocal active
        active = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_cleanup = 0
    while active:
        if time.time() - last_cleanup > 3600:
            from .analytics import cleanup
            cleanup(settings)
            last_cleanup = time.time()
        if not run_once(settings):
            time.sleep(1)


if __name__ == "__main__":
    main()
