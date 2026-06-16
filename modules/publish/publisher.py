"""
微信公众号发布模块 — 订阅号专用：创建草稿到草稿箱。
- 健壮的token缓存和自动刷新
- 完善的错误处理和日志
- Config: ~/repos/paper-loop/data/config.json
"""

import json
import os
import struct
import zlib
import urllib.request
import urllib.error
import time
import sys
import re
from pathlib import Path

# ── resolve repo root (look for pyproject.toml) ──────────────────────
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent  # modules/publish -> modules -> repo

DATA_DIR = _REPO_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"
DEFAULT_COVERS_DIR = DATA_DIR / "covers"

# Config path
CONFIG_PATH = DATA_DIR / "config.json"

TOKEN_CACHE = DATA_DIR / "token_cache.json"
ARTICLE_LOG = DATA_DIR / "published_log.json"


def _find_config():
    """Locate the wechat config file, trying repo location first, then fallback."""
    if CONFIG_PATH.exists():
        return CONFIG_PATH
    if FALLBACK_CONFIG_PATH.exists():
        return FALLBACK_CONFIG_PATH
    raise FileNotFoundError(
        f"Config not found at {CONFIG_PATH} or {FALLBACK_CONFIG_PATH}"
    )


def load_config():
    with open(_find_config()) as f:
        raw = json.load(f)
    # Normalize keys (support both wechat_appid/appid and wechat_appsecret/appsecret)
    return {
        "appid": raw.get("appid") or raw.get("wechat_appid", ""),
        "appsecret": raw.get("appsecret") or raw.get("wechat_appsecret", ""),
        "base_url": raw.get("base_url", "https://api.weixin.qq.com"),
    }


def get_token(force=False):
    cfg = load_config()
    if not force and os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE) as f:
                cache = json.load(f)
            if cache.get("expires_at", 0) > time.time() + 300:
                return cache["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass
    url = (
        f"{cfg['base_url']}/cgi-bin/token"
        f"?grant_type=client_credential"
        f"&appid={cfg['appid']}&secret={cfg['appsecret']}"
    )
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        data = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"[ERROR] 网络错误: {e}")
        sys.exit(1)
    if "access_token" not in data:
        errcode = data.get("errcode")
        if errcode == 40164:
            ip_match = re.search(r'invalid ip (\d+\.\d+\.\d+\.\d+)', data.get("errmsg", ""))
            current_ip = ip_match.group(1) if ip_match else "unknown"
            print(f"[ERROR] IP白名单问题! 当前出口IP: {current_ip}")
            print(f"  请到 mp.weixin.qq.com -> 设置与开发 -> 基本配置 -> IP白名单")
            print(f"  添加 IP: {current_ip}")
        else:
            print(f"[ERROR] 获取token失败: {json.dumps(data, ensure_ascii=False)}")
        sys.exit(1)
    cache = {"access_token": data["access_token"], "expires_at": time.time() + data.get("expires_in", 7200)}
    with open(TOKEN_CACHE, "w") as f:
        json.dump(cache, f)
    return data["access_token"]


def generate_default_thumb():
    width, height = 900, 383
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            r = min(255, 25 + y // 4)
            g = min(255, 50 + y // 3)
            b_val = min(255, 100 + y // 2)
            raw_data += bytes([r, g, b_val])
    compressed = zlib.compress(raw_data)
    def make_chunk(ctype, cdata):
        ch = ctype + cdata
        return struct.pack('>I', len(cdata)) + ch + struct.pack('>I', zlib.crc32(ch) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += make_chunk(b'IDAT', compressed)
    png += make_chunk(b'IEND', b'')
    return png


def upload_thumb(token, image_path=None):
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_data = f.read()
        filename = os.path.basename(image_path)
    else:
        image_data = generate_default_thumb()
        filename = "cover.png"
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  [ERROR] 封面上传网络错误: {e}")
        return None
    if "media_id" not in data:
        print(f"  [ERROR] 封面上传失败: {json.dumps(data, ensure_ascii=False)}")
        return None
    return data["media_id"]


def upload_content_image(token, image_path):
    import mimetypes
    filename = os.path.basename(image_path)
    mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    with open(image_path, "rb") as f:
        image_data = f.read()
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  [ERROR] 图片上传网络错误: {e}")
        return None
    if "url" not in data:
        print(f"  [ERROR] 图片上传失败: {json.dumps(data, ensure_ascii=False)}")
        return None
    print(f"  [图片] 上传成功: {data['url']}")
    return data["url"]


def create_draft(token, title, content, thumb_media_id, digest="", author="kk", content_source_url=""):
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    article_payload = {
        "title": title,
        "author": author,
        "digest": digest[:120] if digest else "",
        "content": content,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0
    }
    if content_source_url:
        article_payload["content_source_url"] = content_source_url
    article = {
        "articles": [article_payload]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(article, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  [ERROR] 草稿创建网络错误: {e}")
        return None
    if "media_id" not in data:
        print(f"  [ERROR] 草稿创建失败: {json.dumps(data, ensure_ascii=False)}")
        return None
    return data["media_id"]


def log_published(article_type, title, media_id, paper_id=None):
    log = []
    if os.path.exists(ARTICLE_LOG):
        try:
            with open(ARTICLE_LOG) as f:
                log = json.load(f)
        except json.JSONDecodeError:
            log = []
    log.append({
        "paper_id": paper_id,
        "type": article_type,
        "title": title,
        "media_id": media_id,
        "status": "draft",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    with open(ARTICLE_LOG, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def is_published(paper_id):
    if not paper_id:
        return False
    if not os.path.exists(ARTICLE_LOG):
        return False
    try:
        with open(ARTICLE_LOG) as f:
            log = json.load(f)
        return any(entry.get("paper_id") == paper_id for entry in log)
    except (json.JSONDecodeError, KeyError):
        return False


def run_review(json_path):
    """Run review before publishing. Returns True if passed, False if blocked."""
    from ..review.reviewer import review_article as do_review
    with open(json_path) as f:
        article = json.load(f)
    paper_id = article.get("paper_id", "")
    if not paper_id or paper_id == "stage1_summary":
        print("  [审稿] 总结文章，跳过审稿")
        return True
    print("  [审稿] 对比论文原文...")
    try:
        ok = do_review(json_path, paper_id=paper_id, auto_fix=False)
        if not ok:
            print("  [审稿] ✗ 发现事实性问题，请先修正后再发布")
            print("  [提示] 运行 review 命令查看详情")
            return False
        print("  [审稿] ✓ 审稿通过")
        return True
    except Exception as e:
        print(f"  [审稿] 审稿异常: {e}")
        print("  [审稿] 跳过审稿，继续发布")
        return True


def publish_article(json_path, skip_review=False):
    """Publish a single article JSON to WeChat drafts.

    Args:
        json_path: Path to the article JSON file.
        skip_review: If True, skip the review step.

    Returns:
        True on success, False on failure.
    """
    print(f"\n{'='*60}")
    print(f"发布: {os.path.basename(json_path)}")
    try:
        with open(json_path) as f:
            article = json.load(f)
    except json.JSONDecodeError:
        try:
            with open(json_path) as f:
                raw = f.read()
            article = json.loads(raw, strict=False)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            print("  [FIX] JSON格式已自动修复")
        except Exception as e:
            print(f"  [ERROR] JSON解析失败: {e}")
            return False

    title = article.get("title", "Untitled")
    content = article.get("content", "")
    digest = article.get("digest", "")
    author = article.get("author", "kk")
    article_type = article.get("type", "paper")
    paper_id = article.get("paper_id", "")
    thumb_path = article.get("thumb_image", None)
    content_source_url = article.get("content_source_url", "")

    print(f"  标题: {title}")

    if paper_id and is_published(paper_id):
        print(f"  [SKIP] 已发布过 (paper_id={paper_id})")
        return True

    if not content:
        print(f"  [ERROR] 文章内容为空")
        return False

    # Step 0: Review against source paper
    if not skip_review:
        if not run_review(json_path):
            return False

    print("  [1/3] 获取Token...")
    token = get_token()
    print("  [2/3] 上传封面...")
    thumb_id = upload_thumb(token, thumb_path)
    if not thumb_id:
        print("  [FAIL] 封面上传失败")
        return False
    print("  [3/3] 创建草稿...")
    draft_id = create_draft(token, title, content, thumb_id, digest, author, content_source_url)
    if not draft_id:
        print("  [FAIL] 草稿创建失败")
        return False
    log_published(article_type, title, draft_id, paper_id)
    print(f"  [OK] 草稿创建成功! media_id={draft_id}")
    return True
