import re
import fitz


class PaperError(ValueError):
    pass


def infer_title(page):
    """Prefer prominent horizontal text, excluding rotated arXiv stamps and long notices."""
    candidates = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0 or block["bbox"][1] > page.rect.height * .55:
            continue
        lines = [line for line in block.get("lines", []) if abs(line.get("dir", (1, 0))[0] - 1) < .01]
        spans = [span for line in lines for span in line.get("spans", [])]
        text = " ".join("".join(span["text"] for span in line["spans"]) for line in lines).strip()
        if 12 <= len(text) <= 300 and spans and not text.lower().startswith(("provided proper attribution", "copyright", "arxiv:")):
            candidates.append((max(s["size"] for s in spans), -block["bbox"][1], text))
    return max(candidates)[2] if candidates else "未命名论文"


def reading_order(items, width):
    """Full-width blocks separate two-column bands; read each column top to bottom."""
    full = sorted([b for b in items if b["bbox"][2] - b["bbox"][0] > width * .64], key=lambda b: b["bbox"][1])
    small = [b for b in items if b not in full]
    output = []
    for separator in full + [None]:
        edge = separator["bbox"][1] if separator else float("inf")
        band = [b for b in small if (b["bbox"][1] + b["bbox"][3]) / 2 < edge]
        small = [b for b in small if b not in band]
        left = [b for b in band if (b["bbox"][0] + b["bbox"][2]) / 2 < width / 2]
        right = [b for b in band if b not in left]
        # Single-column indented paragraphs stay in their natural vertical order.
        is_columns = left and right and max(b["bbox"][2] for b in left) < min(b["bbox"][0] for b in right)
        output.extend(sorted(left, key=lambda b: b["bbox"][1]) + sorted(right, key=lambda b: b["bbox"][1]) if is_columns else sorted(band, key=lambda b: b["bbox"][1]))
        if separator:
            output.append(separator)
    return output


def extract(path, max_pages=100):
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PaperError("文件损坏或不是有效的 PDF，请重新选择文件。") from exc
    with doc:
        if doc.needs_pass:
            raise PaperError("暂不支持加密 PDF，请先解密后再上传。")
        if not 0 < len(doc) <= max_pages:
            raise PaperError(f"请上传 1—{max_pages} 页的论文。")
        pages, blocks = [], []
        for number, page in enumerate(doc, 1):
            rotation = page.rotation
            rect = page.rect
            items = []
            for item in page.get_text("blocks"):
                if item[6] != 0:
                    continue
                text = re.sub(r"(?<=\w)-\n(?=\w)", "", item[4]).strip()
                if len(text) < 3:
                    continue
                # Text coordinates are unrotated; PDF.js displays the rotated page.
                box = fitz.Rect(item[:4]) * page.rotation_matrix if rotation else fitz.Rect(item[:4])
                items.append({"bbox": [round(v, 2) for v in box], "text": text, "page": number})
            items = reading_order(items, rect.width)
            for index, item in enumerate(items):
                item["id"] = f"p{number}-b{index + 1}"
            text_length = sum(len(b["text"]) for b in items)
            pages.append({"number": number, "width": rect.width, "height": rect.height, "parsed": text_length >= 30})
            blocks.extend(items)
        if not any(p["parsed"] for p in pages):
            raise PaperError("未检测到可提取正文，扫描版 PDF 暂不支持，请上传文字版。")
        title = (doc.metadata or {}).get("title", "").strip()
        if not title or title.lower() in {"untitled", "microsoft word"} or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", title):
            title = infer_title(doc[0])[:220]
        return {"title": title, "pages": pages, "blocks": blocks}
