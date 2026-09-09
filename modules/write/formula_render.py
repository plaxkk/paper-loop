"""
LaTeX 公式渲染工具：将文章中的 LaTeX 公式转为微信 CDN 图片。

关键约束：微信文章只接受 mmbiz.qpic.cn 域名的图片，外部 URL 会被吞掉。
因此流程是：CodeCogs 渲染 PNG → 下载本地 → 上传微信 CDN → 替换文章中的公式标记。

文章中的公式标记：
  <p>$$ formula $$</p>  → 块级公式（替换整个 <p> 为居中 CDN 图片）
  文本 $ formula $ 文本  → 行内公式（嵌入文字中）

渲染后端：CodeCogs PNG API → 微信 CDN
"""

import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

# ── resolve repo root ────────────────────────────────────────────────
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent  # modules/write -> modules -> repo

DATA_DIR = _REPO_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"

# Import publisher utilities
from ..publish.publisher import get_token, upload_content_image

# CodeCogs PNG API
# 微信忽略 img CSS 尺寸 → 图片像素大小 = 显示大小
# dpi{150} 保持自然尺寸（≈正文字体），dpi 提升只会等比放大
CODECOGS_PNG = "https://latex.codecogs.com/png.image?\\dpi{{150}}%20\\color{{black}}%20{formula}"

# 块级公式 HTML 模板 — 300 DPI 高清，紧凑显示
BLOCK_FORMULA_TEMPLATE = (
    '<img src="{cdn_url}" '
    'style="display: block; margin: 12px auto; max-width: 60%; height: auto;" '
    'alt="{alt}">'
)

# 行内公式 HTML 模板 — 融入正文，不破坏行间距
INLINE_FORMULA_TEMPLATE = (
    '<img src="{cdn_url}" '
    'style="vertical-align: text-bottom; height: 0.7em;" '
    'alt="{alt}">'
)


def latex_to_codecogs_url(latex: str) -> str:
    """LaTeX → CodeCogs PNG URL（150 DPI，自然尺寸）"""
    encoded = urllib.parse.quote(latex.strip(), safe="")
    return CODECOGS_PNG.format(formula=encoded)


def download_formula_png(url: str) -> str:
    """下载 CodeCogs 渲染的公式 PNG 到临时文件"""
    proxy = urllib.request.ProxyHandler({
        'http': 'http://127.0.0.1:7897',
        'https': 'http://127.0.0.1:7897'
    })
    opener = urllib.request.build_opener(proxy)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req, timeout=15)

    if resp.status != 200:
        raise Exception(f"CodeCogs returned HTTP {resp.status}")

    suffix = '.png'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(resp.read())
        return f.name


def latex_escape_html(text: str) -> str:
    """转义 LaTeX 中可能破坏 HTML 的字符（用于 alt 属性）"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def render_formula_to_cdn(latex: str, token: str) -> str:
    """完整流程：LaTeX → CodeCogs PNG → 下载 → 上传微信 CDN → 返回 CDN URL"""
    codecogs_url = latex_to_codecogs_url(latex)

    try:
        tmp_path = download_formula_png(codecogs_url)
        cdn_url = upload_content_image(token, tmp_path)
        os.unlink(tmp_path)
        return cdn_url
    except Exception as e:
        print(f"  [ERROR] Formula rendering failed: {e}")
        return codecogs_url


def render_formulas_in_article(content: str, token: str, dry_run: bool = False) -> str:
    """将文章 HTML 中的 LaTeX 标记替换为微信 CDN 公式图片"""

    if dry_run:
        block_count = len(re.findall(r'\$\$(.+?)\$\$', content, re.DOTALL))
        inline_count = len(re.findall(r'(?<!\$)\$(.+?)\$(?!\$)', content))
        print(f"  Block formulas ($$...$$): {block_count}")
        print(f"  Inline formulas ($...$): {inline_count}")
        return content

    # 1. 处理块级公式：<p>...$$...$$</p> → 微信 CDN 图片
    def make_block_replacement(leading_text, formula_text):
        cdn_url = render_formula_to_cdn(formula_text.strip(), token)
        alt = latex_escape_html(formula_text.strip())
        img_html = BLOCK_FORMULA_TEMPLATE.format(cdn_url=cdn_url, alt=alt)
        print(f"  [BLOCK] {formula_text.strip()[:50]}... → uploaded")

        if leading_text.strip():
            return f"<p>{leading_text.strip()}</p>\n\n{img_html}\n"
        else:
            return f"\n{img_html}\n"

    content = re.sub(
        r'<p[^>]*>(.*?)\$\$(.+?)\$\$\s*</p>',
        lambda m: make_block_replacement(m.group(1), m.group(2)),
        content,
        flags=re.DOTALL
    )

    # 2. 裸 $$ ... $$（不在 <p> 内）
    def replace_block_bare(match):
        formula = match.group(1).strip()
        cdn_url = render_formula_to_cdn(formula, token)
        alt = latex_escape_html(formula)
        print(f"  [BLOCK-bare] {formula[:50]}... → uploaded")
        return f"\n{BLOCK_FORMULA_TEMPLATE.format(cdn_url=cdn_url, alt=alt)}\n"

    content = re.sub(r'\$\$(.+?)\$\$', replace_block_bare, content, flags=re.DOTALL)

    # 3. 行内公式 $ ... $
    def replace_inline(match):
        formula = match.group(1).strip()
        cdn_url = render_formula_to_cdn(formula, token)
        alt = latex_escape_html(formula)
        print(f"  [INLINE] {formula[:40]}... → uploaded")
        return INLINE_FORMULA_TEMPLATE.format(cdn_url=cdn_url, alt=alt)

    content = re.sub(r'(?<!\$)\$(.+?)\$(?!\$)', replace_inline, content)

    return content


def process_article(json_path: str, dry_run: bool = False) -> dict:
    """处理单篇文章 JSON"""
    with open(json_path, "r", encoding="utf-8") as f:
        article = json.load(f)

    if dry_run:
        render_formulas_in_article(article["content"], token="", dry_run=True)
        return article

    print(f"  Getting WeChat access token...")
    token = get_token()

    old_content = article["content"]
    new_content = render_formulas_in_article(old_content, token, dry_run=False)

    if new_content != old_content:
        article["content"] = new_content
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Updated: {os.path.basename(json_path)}")
    else:
        print(f"  No formulas found")

    return article
