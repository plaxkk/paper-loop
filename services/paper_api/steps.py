"""One model request per durable queue step, within a cloud function's time limit."""
import json
from . import llm
from .db import connection, encode


def metrics_add(total, usage):
    return {key: total.get(key, 0) + usage.get(key, 0) for key in {**total, **usage}}


def checkpoint(settings, job, state):
    with connection(settings, True) as db:
        db.execute("UPDATE jobs SET checkpoint=?,status='queued',lease=NULL,claim=NULL WHERE id=? AND claim=? AND status='running'", (encode(state), job["id"], job["claim"]))
    return None, {}


def summarize(settings, source, blocks):
    result, usage = llm.call(settings, '概括这部分的研究问题、方法、实验与局限。返回 {"notes":[{"text":"中文概括，最多800字","citations":["原文块id"]}]}。最多4条，每条必须有原文依据。', source)
    allowed = {b["id"] for b in blocks}
    if source and "citations" in source[0]:
        allowed &= {ref for note in source for ref in note["citations"]}
    notes = []
    for note in result.get("notes", []):
        if isinstance(note, dict) and isinstance(note.get("text"), str):
            refs = [ref for ref in llm.citations(note.get("citations"), blocks) if ref in allowed]
            if refs:
                notes.append({"text": note["text"][:1600], "citations": refs})
    if not notes:
        raise llm.ModelError("本部分没有返回有效原文依据，请重试。")
    return notes[:4], usage


def advance(settings, job, blocks, payload):
    state = json.loads(job.get("checkpoint") or "{}")
    total = state.get("metrics", {})
    if job["kind"] == "translate":
        chunks = list(llm.batches([b for b in blocks if b["id"] in payload["block_ids"]], 12000))
        offset = state.get("offset", 0)
        if offset >= len(chunks):
            raise llm.ModelError("没有可翻译的段落。")
        batch = chunks[offset]
        result, usage = llm.call(settings, '逐段翻译为中文，保持原意和数字，公式无法还原时保留原文。返回 {"translations":[{"id":"原文块id","text":"中文译文"}]}，每个输入块必须对应一条译文。', llm.evidence(batch))
        values = result.get("translations", [])
        translated = {v.get("id"): v.get("text") for v in values if isinstance(v, dict) and isinstance(v.get("text"), str) and v["text"].strip()}
        if set(translated) != {b["id"] for b in batch}:
            raise llm.ModelError("部分段落没有完整译文，请重试本页。")
        # Preserve split parts of unusually long source blocks under their original id.
        completed = dict(state.get("translated", {}))
        for block in batch:
            key = block["id"]
            completed[key] = (completed.get(key, "") + "\n" + translated[key]).strip()
        total = metrics_add(total, usage)
        if offset + 1 < len(chunks):
            return checkpoint(settings, job, {"offset": offset + 1, "translated": completed, "metrics": total})
        return {"translations": [{"id": key, "text": value} for key, value in completed.items()]}, total

    chunks = list(llm.batches(blocks))
    offset = state.get("offset", 0)
    notes = state.get("notes", [])
    if len(chunks) > 1 and offset < len(chunks):
        part, usage = summarize(settings, llm.evidence(chunks[offset]), blocks)
        return checkpoint(settings, job, {"offset": offset + 1, "notes": notes + part, "metrics": metrics_add(total, usage)})

    # Hierarchically reduce all notes; never silently drop later pages to fit a prompt.
    if len(encode(notes)) > 24000:
        reduced = state.get("reduced", [])
        reduction_offset = state.get("reduction_offset", 0)
        batch, size = [], 0
        for note in notes[reduction_offset:]:
            if batch and size + len(encode(note)) > 16000:
                break
            batch.append(note)
            size += len(encode(note))
        part, usage = summarize(settings, batch, blocks)
        reduced += part
        next_offset = reduction_offset + len(batch)
        state = {"offset": offset, "metrics": metrics_add(total, usage)}
        if next_offset < len(notes):
            state.update(notes=notes, reduced=reduced, reduction_offset=next_offset)
        else:
            if len(encode(reduced)) >= len(encode(notes)):
                raise llm.ModelError("长论文概览未能缩减到可靠范围，请重试。")
            state.update(notes=reduced)
        return checkpoint(settings, job, state)

    source = notes if notes else llm.evidence(blocks)
    result, usage = llm.call(settings, '生成论文概览。返回 {"question":"研究问题", "method":"核心方法", "results":"实验结论及条件", "limitations":"局限与未证明的内容", "claims":[{"title":"重要论点", "explanation":"中文解释及为什么重要", "category":"问题定义/关键方法/实验结果/局限", "citations":["原文块id"]}]}。claims 3至7条，每条必须有原文依据，不把背景说明写成论文结论。', source)
    return llm.overview_result(result, blocks), metrics_add(total, usage)
