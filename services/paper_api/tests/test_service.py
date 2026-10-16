import json
import time
import fitz
import httpx
import pytest
from fastapi.testclient import TestClient
from services.paper_api.app import create_app
from services.paper_api.config import Settings
from services.paper_api.db import connection, encode
from services.paper_api.worker import run_once, claim, execute
from services.paper_api.pdf import extract, PaperError, reading_order
from services.paper_api.sources import arxiv_id, resolve_arxiv
from services.paper_api.analytics import cleanup, report
from services.paper_api import llm


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, api_key="test-only-not-a-real-key")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def paper_bytes():
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((40, 50), "An Evidence-Grounded Study", fontsize=18)
    page.insert_textbox(fitz.Rect(40, 100, 280, 350), "Introduction\nWe study attention mechanisms for sequence learning. Our method compares query and key vectors.\nThe training dataset contains 100 examples. We compare against a recurrent baseline.", fontsize=12)
    page.insert_textbox(fitz.Rect(320, 100, 560, 350), "Results and Limitations\nThe evaluation accuracy is 0.82 on the held-out dataset. This is not evidence of general intelligence.\nWe did not evaluate multilingual transfer or deployment latency.", fontsize=12)
    page = doc.new_page(width=600, height=800)
    page.insert_textbox(fitz.Rect(40, 50, 550, 400), "Appendix A\nWe report an ablation experiment removing position information. Accuracy drops to 0.61.\nThis appendix contains an important limitation: only synthetic data was evaluated.\nThe objective is next-token prediction, and evaluation uses exact-match accuracy.", fontsize=12)
    value = doc.tobytes()
    doc.close()
    return value


def upload(client, paper_bytes):
    response = client.post("/api/imports", files={"file": ("study.pdf", paper_bytes, "application/pdf")}, data={"consent": "true"})
    assert response.status_code == 200, response.text
    return response.json()["workspace_id"]


@pytest.fixture
def fake_model(monkeypatch):
    def fake(settings, instruction, evidence, history=None):
        ids = [b["id"] for b in evidence if "id" in b]
        if "translations" in instruction:
            return {"translations": [{"id": b["id"], "text": "译文：" + b["text"]} for b in evidence]}, {"tokens": 80, "seconds": .1}
        if "claims" in instruction:
            return {"question": "注意力机制研究", "method": "查询与键比较", "results": "准确率为 0.82", "limitations": "仅测试合成数据", "claims": [{"title": f"论点 {i}", "explanation": "来自原文的说明", "category": "关键方法", "citations": [ids[i % len(ids)]]} for i in range(3)]}, {"tokens": 100, "seconds": .1}
        if "notes" in instruction:
            return {"notes": [{"text": "研究方法和局限", "citations": ids}]}, {"tokens": 10, "seconds": .1}
        return {"answer": "论文说明了注意力方法，实验结果有明确条件。", "citations": ids[:2], "category": "机制"}, {"tokens": 40, "seconds": .1}
    monkeypatch.setattr(llm, "call", fake)
    return fake


def ready(client, settings, paper_bytes):
    workspace = upload(client, paper_bytes)
    assert run_once(settings)
    return workspace


def test_upload_parse_analysis_translation_history_delete(client, settings, paper_bytes, fake_model):
    workspace = ready(client, settings, paper_bytes)
    value = client.get(f"/api/workspaces/{workspace}").json()
    assert value["status"] == "ready" and len(value["pages"]) == 2
    assert any("Appendix" in b["text"] for b in value["blocks"])
    assert run_once(settings)
    value = client.get(f"/api/workspaces/{workspace}").json()
    assert len(value["overview"]["claims"]) == 3
    action = client.post(f"/api/workspaces/{workspace}/actions/translate", json={"page": 1}).json()
    assert run_once(settings)
    translated = client.get("/api/jobs/" + action["job_id"]).json()
    assert translated["status"] == "completed"
    assert len(translated["result"]["translations"]) == len([b for b in value["blocks"] if b["page"] == 1])
    assert client.patch(f"/api/workspaces/{workspace}/progress", json={"page": 2}).status_code == 200
    assert client.get(f"/api/workspaces/{workspace}").json()["page"] == 2
    assert client.get(f"/api/workspaces/{workspace}/pdf", headers={"range": "bytes=0-99"}).status_code == 206
    assert client.get("/api/history").json()["items"][0]["id"] == workspace
    assert client.delete(f"/api/workspaces/{workspace}").status_code == 200
    assert not (settings.data_dir / "files" / (workspace + ".pdf")).exists()
    with connection(settings) as db:
        for table in ("workspaces", "messages", "jobs", "events"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_ownership_applies_to_every_private_resource(client, settings, paper_bytes):
    workspace = ready(client, settings, paper_bytes)
    job = client.get(f"/api/workspaces/{workspace}").json()["jobs"][0]["id"]
    with TestClient(create_app(settings)) as stranger:
        for path in (f"/api/workspaces/{workspace}", f"/api/workspaces/{workspace}/pdf", f"/api/jobs/{job}"):
            assert stranger.get(path).status_code == 404
        assert stranger.patch(f"/api/workspaces/{workspace}/progress", json={"page": 1}).status_code == 404
        assert stranger.delete(f"/api/workspaces/{workspace}").status_code == 404
        assert stranger.post(f"/api/workspaces/{workspace}/actions/chat", json={"question": "test"}).status_code == 404
        assert stranger.get("/api/history").json()["items"] == []


def test_dedup_and_quota_are_atomic(client, settings, paper_bytes):
    workspace = upload(client, paper_bytes)
    assert upload(client, paper_bytes) == workspace
    assert client.get("/api/session").json()["remaining_imports"] == 2
    settings.daily_imports = 1
    assert client.post("/api/imports", data={"arxiv": "1706.03762", "consent": "true"}).status_code == 429
    assert not list((settings.data_dir / "files").glob("*.upload"))


def test_csrf_consent_missing_model_and_invalid_inputs(client, settings, paper_bytes):
    assert client.post("/api/imports", data={"arxiv": "1706.03762"}).status_code == 400
    assert client.post("/api/imports", data={"arxiv": "https://localhost/private", "consent": "true"}).status_code == 400
    assert client.post("/api/events", json={"kind": "reader_open"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/events", json={"kind": "reader_open"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    workspace = ready(client, settings, paper_bytes)
    settings.api_key = ""
    assert client.post(f"/api/workspaces/{workspace}/actions/chat", json={"question": "What?"}).status_code == 503
    assert client.get(f"/api/workspaces/{workspace}/pdf").status_code == 200


def test_worker_restart_and_delete_race(client, settings, paper_bytes, fake_model):
    workspace = upload(client, paper_bytes)
    job = claim(settings)
    with connection(settings, True) as db:
        db.execute("UPDATE jobs SET lease=0 WHERE id=?", (job["id"],))
    newer = claim(settings)
    assert newer["id"] == job["id"] and newer["claim"] != job["claim"]
    execute(settings, job)
    assert client.get(f"/api/workspaces/{workspace}").json()["status"] == "queued"
    client.delete(f"/api/workspaces/{workspace}")
    execute(settings, newer)
    assert not (settings.data_dir / "files" / (workspace + ".pdf")).exists()
    assert client.get("/api/history").json()["items"] == []


def test_model_bad_citations_rejected(settings, paper_bytes, tmp_path, monkeypatch):
    path = tmp_path / "source.pdf"
    path.write_bytes(paper_bytes)
    blocks = extract(path)["blocks"]
    monkeypatch.setattr(llm, "call", lambda *_: ({"claims": [{"title": "invented", "explanation": "invalid", "citations": ["p999-b1"]}]}, {"tokens": 1, "seconds": .1}))
    with pytest.raises(llm.ModelError):
        llm.analyze(settings, blocks)


def test_long_paper_not_truncated_and_double_column(tmp_path):
    items = [{"text": "L1", "bbox": [40, 100, 250, 130]}, {"text": "R1", "bbox": [320, 100, 550, 130]}, {"text": "L2", "bbox": [40, 150, 250, 180]}, {"text": "R2", "bbox": [320, 150, 550, 180]}]
    assert [b["text"] for b in reading_order(items, 600)] == ["L1", "L2", "R1", "R2"]
    doc = fitz.open()
    for i in range(30):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(40, 40, 550, 780), (f"Page {i} study evidence and experimental limitations. " * 40), fontsize=9)
    path = tmp_path / "long.pdf"
    doc.save(path)
    value = extract(path)
    assert sum(len(b["text"]) for b in value["blocks"]) > 15000
    assert value["blocks"][-1]["page"] == 30


def test_scanned_encrypted_corrupt_and_oversized(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-not-a-real-document")
    with pytest.raises(PaperError):
        extract(path)
    doc = fitz.open()
    doc.new_page()
    doc.save(path, incremental=False)
    with pytest.raises(PaperError, match="扫描"):
        extract(path)
    doc.save(tmp_path / "encrypted.pdf", encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    with pytest.raises(PaperError, match="加密"):
        extract(tmp_path / "encrypted.pdf")
    with pytest.raises(PaperError, match="页"):
        extract(path, max_pages=0)


def test_retention_and_cleanup_idempotence(client, settings, paper_bytes, fake_model):
    workspace = ready(client, settings, paper_bytes)
    old = time.time() - 31 * 86400
    with connection(settings, True) as db:
        db.execute("UPDATE workspaces SET created=?", (old,))
        db.execute("UPDATE events SET created=?", (old,))
    assert cleanup(settings) == 1
    assert cleanup(settings) == 0
    assert not (settings.data_dir / "files" / (workspace + ".pdf")).exists()
    daily = report(settings)["daily"]
    assert sum(r["value"] for r in daily if r["kind"] == "import_success") == 1


def test_failed_action_retry_keeps_previous_pages_and_single_message(client, settings, paper_bytes, fake_model, monkeypatch):
    workspace = ready(client, settings, paper_bytes)
    run_once(settings)
    first = client.post(f"/api/workspaces/{workspace}/actions/translate", json={"page": 1}).json()["job_id"]
    run_once(settings)
    def unavailable(*args, **kwargs):
        raise llm.ModelError("模型暂时无法完成请求，请稍后重试。")
    monkeypatch.setattr(llm, "call", unavailable)
    chat = client.post(f"/api/workspaces/{workspace}/actions/chat", json={"question": "Explain the result", "request_id": "retry-me"}).json()["job_id"]
    run_once(settings)
    assert client.get(f"/api/jobs/{chat}").json()["status"] == "failed"
    assert client.get(f"/api/jobs/{first}").json()["status"] == "completed"
    with TestClient(create_app(settings)) as stranger:
        assert stranger.post(f"/api/jobs/{chat}/retry").status_code == 404
    monkeypatch.setattr(llm, "call", fake_model)
    assert client.post(f"/api/jobs/{chat}/retry").json()["job_id"] == chat
    run_once(settings)
    messages = client.get(f"/api/workspaces/{workspace}").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_invalid_block_and_page_rejected(client, settings, paper_bytes, fake_model):
    workspace = ready(client, settings, paper_bytes)
    assert client.post(f"/api/workspaces/{workspace}/actions/translate", json={"block_ids": ["p999-b1"]}).status_code == 400
    assert client.post(f"/api/workspaces/{workspace}/actions/translate", json={"page": 50}).status_code == 400
    assert client.patch(f"/api/workspaces/{workspace}/progress", json={"page": 50}).status_code == 400


def test_rotated_page_coordinates_align_with_display(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=300, height=500)
    page.insert_text((30, 60), "A paragraph with enough selectable original paper text.")
    page.set_rotation(90)
    path = tmp_path / "rotated.pdf"
    doc.save(path)
    value = extract(path)
    assert value["pages"][0]["width"] == 500
    assert value["pages"][0]["height"] == 300
    box = value["blocks"][0]["bbox"]
    assert 0 <= box[0] < box[2] <= 500
    assert 0 <= box[1] < box[3] <= 300


def test_title_skips_copyright_notice_and_rotated_stamp(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((40, 35), "Provided proper attribution is provided, reproduction is permitted.", fontsize=10)
    page.insert_text((80, 120), "Attention Is All You Need", fontsize=19)
    page.insert_text((25, 600), "arXiv:1706.03762v7", fontsize=24, rotate=90)
    page.insert_text((80, 190), "Several authors and an abstract describing the proposed study.", fontsize=11)
    path = tmp_path / "title.pdf"
    doc.save(path)
    assert extract(path)["title"] == "Attention Is All You Need"


@pytest.mark.parametrize("source,expected", [("1706.03762", "1706.03762"), ("https://arxiv.org/abs/1706.03762v7", "1706.03762v7"), ("https://arxiv.org/pdf/1706.03762.pdf", "1706.03762"), ("https://arxiv.org/pdf/1706.03762v7", "1706.03762v7"), ("cs/9901001v2", "cs/9901001v2")])
def test_arxiv_normalization(source, expected):
    assert arxiv_id(source) == expected


@pytest.mark.parametrize("source", ["http://arxiv.org/abs/1706.03762", "https://arxiv.org.evil.test/abs/1706.03762", "https://arxiv.org@localhost/abs/1706.03762", "https://arxiv.org/abs/1706.03762?url=http://localhost", "file:///private/secret", "https://127.0.0.1/pdf/1706.03762"])
def test_arbitrary_url_rejected(source):
    with pytest.raises(PaperError):
        arxiv_id(source)


def test_arxiv_version_falls_back_to_official_abstract():
    def handler(request):
        if request.url.host == "export.arxiv.org":
            raise httpx.ConnectError("upstream unavailable", request=request)
        assert str(request.url) == "https://arxiv.org/abs/1706.03762"
        return httpx.Response(200, text='<a href="/abs/1706.03762v1">v1</a> Cite arXiv:1706.03762v7')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert resolve_arxiv("1706.03762", client) == "1706.03762v7"


QUESTIONS = [
    "研究问题是什么？", "为什么使用注意力？", "方法怎样比较查询与键？", "什么是序列学习？", "训练目标是什么？",
    "训练数据量是多少？", "实验比较了哪个基线？", "准确率是多少？", "实验支持什么结论？", "是否证明通用智能？",
    "有哪些未评估的能力？", "是否评估多语言？", "是否测量部署延迟？", "附录研究什么？", "附录消融移除了什么？",
    "消融后的准确率是多少？", "数据是否为真实数据？", "数据有哪些局限？", "评估指标是什么？", "是否使用精确匹配？",
    "如何解释方法机制？", "哪些内容属于背景？", "能提供段落依据吗？", "结果是否能推广？", "实现需要哪些输入？",
    "公式是什么意思？", "与循环模型如何比较？", "跨页总结主要结论？", "论文是否证明未报告的实验？", "还有哪些证据不足？",
]


@pytest.mark.parametrize("question", QUESTIONS)
def test_30_question_protocol_and_citations(client, settings, paper_bytes, fake_model, question):
    workspace = ready(client, settings, paper_bytes)
    run_once(settings)
    result = client.post(f"/api/workspaces/{workspace}/actions/chat", json={"question": question, "request_id": "same-request"})
    assert result.status_code == 200
    assert client.post(f"/api/workspaces/{workspace}/actions/chat", json={"question": question, "request_id": "same-request"}).json() == result.json()
    run_once(settings)
    value = client.get(f"/api/workspaces/{workspace}").json()
    assert [m["role"] for m in value["messages"]] == ["user", "assistant"]
    assert set(value["messages"][1]["citations"]) <= {b["id"] for b in value["blocks"]}
    with connection(settings) as db:
        # Raw questions live only in private messages/payloads, never analytics events.
        assert question not in encode([dict(r) for r in db.execute("SELECT * FROM events")])
