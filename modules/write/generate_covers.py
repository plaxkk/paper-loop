"""Generate cover images for WeChat articles with title text overlay."""

import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── resolve repo root ────────────────────────────────────────────────
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent  # modules/write -> modules -> repo

DATA_DIR = _REPO_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"
THUMB_COVERS_DIR = DATA_DIR / "covers"              # 推文卡片封面（thumb_image）
HEADER_COVERS_DIR = DATA_DIR / "images" / "covers"  # 文章内部文首第一张图

# Article-specific color themes
COLOR_THEMES = {
    "P1": {"bg": (15, 23, 42), "accent": (59, 130, 246), "subtitle": "Attention Is All You Need"},
    "P2": {"bg": (20, 10, 35), "accent": (168, 85, 247), "subtitle": "BERT"},
    "P3": {"bg": (10, 30, 20), "accent": (34, 197, 94), "subtitle": "GPT-1"},
    "P4": {"bg": (30, 15, 10), "accent": (249, 115, 22), "subtitle": "GPT-2"},
    "P5": {"bg": (35, 10, 15), "accent": (239, 68, 68), "subtitle": "GPT-3"},
    "P6": {"bg": (15, 20, 35), "accent": (14, 165, 233), "subtitle": "Scaling Laws"},
    "P7": {"bg": (25, 25, 10), "accent": (234, 179, 8), "subtitle": "Chinchilla"},
    "P8": {"bg": (10, 25, 30), "accent": (6, 182, 212), "subtitle": "FlashAttention"},
    "P9": {"bg": (20, 15, 30), "accent": (139, 92, 246), "subtitle": "FlashAttention-2"},
    "P10": {"bg": (25, 10, 25), "accent": (236, 72, 153), "subtitle": "ZeRO"},
    "P11": {"bg": (25, 15, 15), "accent": (239, 68, 68), "subtitle": "InstructGPT"},
    "P12": {"bg": (10, 25, 25), "accent": (20, 184, 166), "subtitle": "Constitutional AI"},
    "P13": {"bg": (25, 20, 10), "accent": (251, 146, 60), "subtitle": "DPO"},
    "stage1_summary": {"bg": (20, 15, 30), "accent": (139, 92, 246), "subtitle": "Stage 1 Summary"},
    "stage2_summary": {"bg": (15, 20, 35), "accent": (14, 165, 233), "subtitle": "Stage 2 Summary"},
}

PAPER_NUMBERS = {
    "P1": "01", "P2": "02", "P3": "03", "P4": "04",
    "P5": "05", "P6": "06", "P7": "07", "P8": "08",
    "P9": "09", "P10": "10", "P11": "11", "P12": "12", "P13": "13",
    "stage1_summary": "S1", "stage2_summary": "S2",
}


def generate_cover(paper_id, title, theme=None):
    """Generate a cover image for an article."""
    if theme is None:
        theme = COLOR_THEMES.get(paper_id, {"bg": (20, 20, 20), "accent": (100, 100, 100), "subtitle": ""})

    width, height = 900, 383
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Background gradient
    bg = theme["bg"]
    accent = theme["accent"]
    for y in range(height):
        ratio = y / height
        r = int(bg[0] * (1 - ratio * 0.3))
        g = int(bg[1] * (1 - ratio * 0.3))
        b = int(bg[2] * (1 - ratio * 0.3))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Accent line at top
    draw.rectangle([(0, 0), (width, 4)], fill=accent)

    # Subtle accent glow in bottom right
    for i in range(80):
        alpha = max(0, 60 - i)
        color = (
            min(255, bg[0] + accent[0] * alpha // 255),
            min(255, bg[1] + accent[1] * alpha // 255),
            min(255, bg[2] + accent[2] * alpha // 255),
        )
        x = width - 200 + i * 2
        draw.line([(x, height - 60 - i), (x, height)], fill=color, width=2)

    # Load fonts
    try:
        font_path = "/System/Library/Fonts/PingFang.ttc"
        font_bold = ImageFont.truetype(font_path, 36, index=1)
        font_medium = ImageFont.truetype(font_path, 24, index=0)
        font_small = ImageFont.truetype(font_path, 16, index=0)
        font_number = ImageFont.truetype(font_path, 60, index=1)
    except Exception:
        font_bold = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_number = ImageFont.load_default()

    # Paper number (big, faded, top-right)
    num = PAPER_NUMBERS.get(paper_id, "")
    if num:
        draw.text((width - 100, 15), num, fill=(*accent, 40), font=font_number, anchor="rt")

    # Main title - word wrap
    max_chars_per_line = 20
    title_lines = []
    remaining = title
    while remaining:
        if len(remaining) <= max_chars_per_line:
            title_lines.append(remaining)
            break
        break_point = max_chars_per_line
        for i in range(max_chars_per_line, max(max_chars_per_line - 8, 0), -1):
            if remaining[i-1] in '，。！？、；：':
                break_point = i
                break
        title_lines.append(remaining[:break_point])
        remaining = remaining[break_point:]

    y_start = 60
    for i, line in enumerate(title_lines):
        color = (255, 255, 255) if i == 0 else (220, 220, 220)
        draw.text((50, y_start + i * 48), line, fill=color, font=font_bold)

    # Accent line separator
    sep_y = y_start + len(title_lines) * 48 + 10
    draw.rectangle([(50, sep_y), (150, sep_y + 3)], fill=accent)

    # Subtitle / paper name
    subtitle = theme.get("subtitle", "")
    if subtitle:
        draw.text((50, sep_y + 15), subtitle, fill=(*accent,), font=font_medium)

    # Bottom tag
    draw.text((50, height - 35), "kk的大模型论文学习笔记", fill=(150, 150, 150), font=font_small)

    return img


def generate_all_covers():
    """Generate cover images for all articles in data/articles/."""
    os.makedirs(THUMB_COVERS_DIR, exist_ok=True)
    os.makedirs(HEADER_COVERS_DIR, exist_ok=True)

    if not ARTICLES_DIR.exists():
        print(f"文章目录不存在: {ARTICLES_DIR}")
        return

    targets = [f for f in os.listdir(ARTICLES_DIR) if f.endswith(".json")]

    for filename in targets:
        filepath = ARTICLES_DIR / filename

        with open(filepath) as f:
            article = json.load(f)

        paper_id = article.get("paper_id", "")
        title = article.get("title", "Untitled")

        if not paper_id:
            print(f"[SKIP] No paper_id: {filename}")
            continue

        img = generate_cover(paper_id, title)

        # Save thumb cover
        thumb_path = THUMB_COVERS_DIR / f"{paper_id}_cover.png"
        img.save(thumb_path, "PNG")
        print(f"[OK] {paper_id}: thumb -> {thumb_path}")

        # Save header cover
        header_path = HEADER_COVERS_DIR / f"{paper_id}_cover.png"
        img.save(header_path, "PNG")
        print(f"     header -> {header_path}")

        # Update article JSON with thumb_image path
        article["thumb_image"] = str(thumb_path)
        with open(filepath, "w") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"     Updated {filename} with thumb_image")
