#!/usr/bin/env python3
"""
微信公众号数据采集服务
- 接收 Tampermonkey 脚本从浏览器发送的 API 响应数据
- 保存原始 JSON + 合并 latest 快照
- Hermes 直接读取 latest 文件做分析
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "mp_raw"
LATEST_FILE = BASE_DIR / "data" / "mp_analytics_latest.json"
LOG_FILE = BASE_DIR / "data" / "mp_collector.log"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class CollectorHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/mp-data":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"invalid json"}')
            return

        # Save raw file with timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        page_type = payload.get("page_type", "unknown")
        raw_file = DATA_DIR / f"{ts}_{page_type}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Update merged latest
        latest = {}
        if LATEST_FILE.exists():
            try:
                latest = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        latest.setdefault("sections", {})
        latest["sections"][page_type] = {
            "last_updated": ts,
            "url": payload.get("url", ""),
            "api_responses": payload.get("api_responses", []),
            "page_data": payload.get("page_data", {}),
            "title": payload.get("title", ""),
        }
        latest["last_collected"] = ts

        with open(LATEST_FILE, "w", encoding="utf-8") as f:
            json.dump(latest, f, ensure_ascii=False, indent=2)

        log(f"Received {page_type} — saved {raw_file.name} ({content_length} bytes)")

        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "file": str(raw_file)}).encode())

        # Auto-parse into structured DB
        if page_type == "content_analysis":
            try:
                from .schema import init_db, parse_content_analysis, store_parsed
                init_db()
                parsed = parse_content_analysis(raw_file)
                counts = store_parsed(parsed, raw_file)
                log(f"  → content parsed: {counts}")
            except Exception as e:
                log(f"  → content parse failed: {e}")
        elif page_type == "user_analysis":
            try:
                from .schema import init_db, parse_user_analysis, store_parsed
                init_db()
                parsed = parse_user_analysis(raw_file)
                counts = store_parsed(parsed, raw_file)
                log(f"  → user parsed: {counts}")
            except Exception as e:
                log(f"  → user parse failed: {e}")
        elif page_type == "published_records":
            try:
                from .schema import init_db, import_published_records
                init_db()
                data = json.loads(raw_file.read_text(encoding="utf-8"))
                added, updated = import_published_records(data)
                log(f"  → published records: {added} new, {updated} updated")
            except Exception as e:
                log(f"  → published records parse failed: {e}")

    def log_message(self, format, *args):
        pass  # suppress default logging


def start_collector():
    port = 9876
    server = HTTPServer(("127.0.0.1", port), CollectorHandler)
    log(f"MP Data Collector started on http://127.0.0.1:{port}")
    log(f"Data dir: {DATA_DIR}")
    log(f"Latest file: {LATEST_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    start_collector()
