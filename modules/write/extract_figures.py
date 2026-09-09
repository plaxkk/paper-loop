"""
精准裁剪论文PDF中的原始Figure图片，上传微信CDN，替换文章占位符。
策略：根据Figure caption的Y坐标，向上取到上一个文本块或页面顶部作为图的上边界，
      caption作为下边界，精确裁剪。
"""

import fitz
import json
import os
import sys
import re
from pathlib import Path

# ── resolve repo root ────────────────────────────────────────────────
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent  # modules/write -> modules -> repo

DATA_DIR = _REPO_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"
IMAGES_DIR = DATA_DIR / "images"

# Import publisher utilities
from ..publish.publisher import get_token, upload_content_image


def find_figure_bounds(pdf_path, page_num, caption_y_start, caption_y_end, page_width):
    """Find the top boundary of a figure by looking upward from the caption.

    Key insight: figures often contain short text labels (e.g. "Response", "Q", "K", "V")
    that PyMuPDF detects as text blocks. We must skip these figure-internal labels and
    find the first real body-text block above the figure to use as the boundary.

    A block is considered a "figure label" if it's short (<40 chars), single-line (<20px),
    and not a section header (doesn't start with a number like "1 Introduction").

    Additionally, if ALL blocks above the caption are short (<80 chars each) and there
    are more than 3 of them, treat the whole area as figure content — this handles
    flowcharts where multi-line box labels can look deceptively like body text.
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    # Collect all text blocks with their content metadata
    blocks_data = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] == 0:
            text = " ".join(span["text"] for line in b["lines"] for span in line["spans"]).strip()
            rect = fitz.Rect(b["bbox"])
            blocks_data.append({
                "text": text,
                "rect": rect,
                "height": rect.y1 - rect.y0,
            })

    # Sort by top Y
    blocks_data.sort(key=lambda b: b["rect"].y0)

    # Find all blocks above the caption (strictly above, with 5px tolerance)
    above_caption = [b for b in blocks_data if b["rect"].y1 < caption_y_start - 5]

    figure_top = 50  # default: near page top

    if above_caption:
        # Check if ALL blocks above caption are likely figure-internal
        has_real_paragraph = any(len(b["text"]) > 80 for b in above_caption)
        short_count = sum(1 for b in above_caption if len(b["text"]) < 40)

        if not has_real_paragraph and short_count >= 3:
            figure_top = 50
        else:
            for b in reversed(above_caption):
                text = b["text"]
                is_figure_label = (
                    len(text) < 40 and
                    b["height"] < 20 and
                    not re.match(r"^\d+[\.\s]", text)
                )
                if not is_figure_label:
                    figure_top = b["rect"].y1 + 10
                    break

    # Safety: if figure_top is too close to the caption, fall back to page top
    if figure_top >= caption_y_start - 10:
        figure_top = 50

    doc.close()

    figure_region = fitz.Rect(
        40,
        figure_top,
        page_width - 40,
        caption_y_start - 8
    )
    return figure_region


def extract_figure(pdf_path, page_num, region, output_path, zoom=3):
    """Render a precise region of a PDF page at high quality."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=region)
    pix.save(output_path)
    doc.close()
    return output_path


def get_page_text_blocks(pdf_path, page_num):
    """Get all text blocks on a page with their positions."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    blocks = page.get_text("dict")["blocks"]
    result = []
    for b in blocks:
        if b["type"] == 0:
            for line in b["lines"]:
                text = " ".join(span["text"] for span in line["spans"]).strip()
                if text:
                    result.append({
                        "text": text,
                        "bbox": fitz.Rect(b["bbox"]),
                    })
    doc.close()
    return result


# ============================================================
# Define exactly which figures to extract for each paper
# ============================================================
FIGURE_DEFS = {
    "P6": {
        "pdf": "/tmp/P6_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 2,
                "caption_y_start": 210,
                "caption_y_end": 253,
                "description": "Scaling Laws核心幂律关系图 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 11,
                "caption_y_start": 246,
                "caption_y_end": 289,
                "description": "Scaling Laws计算预算分配 (Figure 10)",
            },
        ]
    },
    "P7": {
        "pdf": "/tmp/P7_paper.pdf",
        "page_width": 595,
        "page_height": 842,
        "figures": [
            {
                "name": "fig1",
                "page": 1,
                "caption_y_start": 295,
                "caption_y_end": 374,
                "description": "Chinchilla预测对比图 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 5,
                "caption_y_start": 224,
                "caption_y_end": 304,
                "description": "IsoFLOP曲线与最优模型大小 (Figure 3)",
            },
        ]
    },
    "P8": {
        "pdf": "/tmp/P8_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 1,
                "caption_y_start": 236,
                "caption_y_end": 320,
                "description": "FlashAttention GPU内存层级与分块策略 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 5,
                "caption_y_start": 154,
                "caption_y_end": 209,
                "description": "FlashAttention运行时对比 (Figure 2)",
            },
            {
                "name": "fig3",
                "page": 8,
                "caption_y_start": 204,
                "caption_y_end": 214,
                "description": "FlashAttention加速效果 (Figure 3)",
            },
        ]
    },
    "P9": {
        "pdf": "/tmp/P9_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 3,
                "caption_y_start": 627,
                "caption_y_end": 686,
                "description": "FlashAttention-2前向传播分块示意图 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 7,
                "caption_y_start": 609,
                "caption_y_end": 642,
                "description": "FlashAttention-2并行化策略 (Figure 2)",
            },
            {
                "name": "fig3",
                "page": 8,
                "caption_y_start": 436,
                "caption_y_end": 446,
                "description": "FlashAttention-2工作分配策略 (Figure 3)",
            },
        ]
    },
    "P10": {
        "pdf": "/tmp/P10_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 2,
                "caption_y_start": 302,
                "caption_y_end": 359,
                "description": "ZeRO三阶段显存对比 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 3,
                "caption_y_start": 277,
                "caption_y_end": 311,
                "description": "ZeRO训练吞吐量 (Figure 2)",
            },
        ]
    },
    "P11": {
        "pdf": "/tmp/P11_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 1,
                "caption_y_start": 257,
                "caption_y_end": 311,
                "description": "InstructGPT人类评估结果 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 2,
                "caption_y_start": 305,
                "caption_y_end": 358,
                "description": "RLHF三步训练流程图 (Figure 2)",
            },
        ]
    },
    "P12": {
        "pdf": "/tmp/P12_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 1,
                "caption_y_start": 250,
                "caption_y_end": 315,
                "description": "Constitutional AI两阶段流程 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 2,
                "caption_y_start": 272,
                "caption_y_end": 358,
                "description": "CAI安全性与有用性Elo对比 (Figure 2)",
            },
        ]
    },
    "P13": {
        "pdf": "/tmp/P13_paper.pdf",
        "page_width": 612,
        "page_height": 792,
        "figures": [
            {
                "name": "fig1",
                "page": 1,
                "caption_y_start": 159,
                "caption_y_end": 207,
                "description": "DPO与RLHF对比示意图 (Figure 1)",
            },
            {
                "name": "fig2",
                "page": 6,
                "caption_y_start": 228,
                "caption_y_end": 267,
                "description": "DPO奖励前沿与KL散度 (Figure 2)",
            },
        ]
    },
}


def process_paper(paper_id):
    """Extract clean figures from paper PDF and upload to CDN."""
    config = FIGURE_DEFS[paper_id]
    pdf_path = config["pdf"]
    pw, ph = config["page_width"], config["page_height"]

    out_dir = IMAGES_DIR / paper_id
    os.makedirs(out_dir, exist_ok=True)

    uploaded = {}

    for fig_def in config["figures"]:
        name = fig_def["name"]
        page_num = fig_def["page"]
        output_path = out_dir / f"{paper_id}_{name}_clean.png"

        region = find_figure_bounds(
            pdf_path, page_num,
            fig_def["caption_y_start"],
            fig_def["caption_y_end"],
            pw
        )

        region = fitz.Rect(
            max(0, region.x0),
            max(0, region.y0),
            min(pw, region.x1),
            min(ph, region.y1)
        )

        print(f"  {name}: page {page_num+1}, region={region}")

        extract_figure(pdf_path, page_num, region, str(output_path), zoom=3)
        size_kb = os.path.getsize(output_path) // 1024

        if size_kb < 5:
            print(f"    WARNING: image too small ({size_kb}KB), trying wider region")
            region = fitz.Rect(20, 50, pw - 20, fig_def["caption_y_start"] - 5)
            extract_figure(pdf_path, page_num, region, str(output_path), zoom=3)
            size_kb = os.path.getsize(output_path) // 1024

        print(f"    -> {output_path} ({size_kb}KB)")

        token = get_token()
        cdn_url = upload_content_image(token, str(output_path))
        if cdn_url:
            uploaded[name] = cdn_url
            print(f"    -> CDN uploaded OK")
        else:
            print(f"    -> CDN upload FAILED")

    return uploaded


def replace_figure_in_article(paper_id, uploaded):
    """Replace the figure images (NOT the header) in article JSON."""
    import glob
    if paper_id == "stage2_summary":
        article_path = ARTICLES_DIR / "stage2_summary.json"
    else:
        articles = glob.glob(str(ARTICLES_DIR / f"{paper_id}_*.json"))
        if not articles:
            print(f"  [WARN] No article found for {paper_id}")
            return
        article_path = articles[0]

    with open(article_path, 'r') as f:
        data = json.load(f)

    content = data["content"]

    figures = list(re.finditer(r'<figure[^>]*>\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"', content))

    if not figures:
        figures = list(re.finditer(r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"', content))

    changed = False
    fig_keys = sorted(uploaded.keys())

    body_figures = figures[1:]  # skip header

    for i, match in enumerate(body_figures):
        if i >= len(fig_keys):
            break
        key = fig_keys[i]
        cdn_url = uploaded[key]
        if not cdn_url:
            continue

        old_src = match.group(1)
        old_alt = match.group(2)

        content = content.replace(f'src="{old_src}"', f'src="{cdn_url}"', 1)
        changed = True
        print(f"  Replaced figure {i+1} (alt='{old_alt[:30]}') -> CDN")

    if changed:
        data["content"] = content
        with open(article_path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [OK] Article updated: {os.path.basename(article_path)}")
    else:
        print(f"  [SKIP] No changes")
