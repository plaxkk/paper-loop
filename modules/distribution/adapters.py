#!/usr/bin/env python3
"""
Content adapter: converts WeChat HTML articles to platform-specific formats.

WeChat HTML → {zhihu_md, juejin_md, csdn_md, plain_text}
Handles: figure/images, formulas, internal links, code blocks, styles.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional


def strip_html_tags(html: str) -> str:
    """Remove HTML tags, keeping text content."""
    text = html
    # Remove figure blocks with figcaptions preserved
    text = re.sub(
        r'<figure[^>]*>.*?<figcaption[^>]*>(.*?)</figcaption>.*?</figure>',
        lambda m: '[图: ' + m.group(1).strip() + ']',
        text, flags=re.DOTALL
    )
    text = re.sub(r'<figure[^>]*>.*?</figure>', '', text, flags=re.DOTALL)
    # Convert common tags
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n\n', text)
    text = re.sub(r'</p>', '', text)
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text)
    text = re.sub(r'<hr[^>]*>', '\n\n---\n\n', text)
    text = re.sub(r'<div[^>]*>', '\n\n', text)
    text = re.sub(r'</div>', '', text)
    text = re.sub(r'<section[^>]*>', '', text)
    text = re.sub(r'</section>', '', text)
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r'[图: \1]', text)
    # Clean up entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_judgment(html: str) -> Optional[str]:
    """Extract the screenshot-worthy judgment from dark-background block."""
    m = re.search(
        r'<strong style="font-size: 16px; color: #e0e0e0[^"]*">(.*?)</strong>',
        html, re.DOTALL
    )
    if m:
        return m.group(1).strip()
    return None


def _extract_paper_link(html: str) -> Optional[str]:
    """Extract arXiv paper link from article footer."""
    m = re.search(r'论文链接[：:]\s*<span[^>]*>([^<]+)</span>', html)
    if m:
        return m.group(1).strip()
    return None


def _clean_nav_elements(text: str) -> str:
    """Remove navigation elements from body text."""
    text = re.sub(r'[📖📚][^\n]*\n?', '', text)
    text = re.sub(r'←\s*上一篇[^\n]*\n?', '', text)
    text = re.sub(r'下一篇[^\n]*\s*→\n?', '', text)
    text = re.sub(r'在公众号内回复[^\n]*\n?', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def to_zhihu_markdown(article: dict) -> str:
    """Convert article JSON to Zhihu-flavored markdown."""
    title = article.get("title", "")
    content = article.get("content", "")
    digest = article.get("digest", "")
    paper_link = _extract_paper_link(content)
    body_text = strip_html_tags(content)
    
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    
    if digest:
        lines.append(f"> {digest}")
        lines.append("")
    
    judgment = _extract_judgment(content)
    if judgment:
        lines.append(f"**{judgment}**")
        lines.append("")
    
    body = _clean_nav_elements(body_text)
    lines.append(body)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本文首发于微信公众号「翩然起舞」。*")
    if paper_link:
        lines.append(f"*论文链接: {paper_link}*")
    
    return "\n\n".join(lines)


def to_juejin_markdown(article: dict) -> str:
    """Convert article JSON to Juejin-compatible markdown."""
    title = article.get("title", "")
    content = article.get("content", "")
    digest = article.get("digest", "")
    paper_link = _extract_paper_link(content)
    body_text = strip_html_tags(content)
    
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    
    if digest:
        lines.append(f"> {digest}")
        lines.append("")
    
    judgment = _extract_judgment(content)
    if judgment:
        lines.append(f"> **{judgment}**")
        lines.append("")
    
    body = _clean_nav_elements(body_text)
    lines.append(body)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**关于作者**")
    lines.append("后端工程师，从零学习 AI。关注微信公众号「翩然起舞」获取更多深度解读。")
    if paper_link:
        lines.append(f"论文: {paper_link}")
    
    return "\n\n".join(lines)


def to_csdn_markdown(article: dict) -> str:
    """Convert article JSON to CSDN-compatible markdown."""
    title = article.get("title", "")
    content = article.get("content", "")
    paper_link = _extract_paper_link(content)
    body_text = strip_html_tags(content)
    
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    
    judgment = _extract_judgment(content)
    if judgment:
        lines.append(f"**{judgment}**")
        lines.append("")
    
    body = _clean_nav_elements(body_text)
    lines.append(body)
    lines.append("")
    if paper_link:
        lines.append(f"论文链接: {paper_link}")
    
    return "\n\n".join(lines)


def to_plain_text(article: dict) -> str:
    """Convert article to plain text."""
    return _clean_nav_elements(strip_html_tags(article.get("content", "")))


def adapt_for_all_platforms(article_path: str, output_dir: str = None) -> dict:
    """Read article JSON, generate all platform versions."""
    with open(article_path, encoding="utf-8") as f:
        article = json.load(f)
    
    result = {
        "title": article.get("title", ""),
        "paper_id": article.get("paper_id", ""),
        "zhihu": to_zhihu_markdown(article),
        "juejin": to_juejin_markdown(article),
        "csdn": to_csdn_markdown(article),
        "plain": to_plain_text(article),
    }
    
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        pid = article.get("paper_id", "unknown")
        for platform in ["zhihu", "juejin", "csdn", "plain"]:
            ext = ".md" if platform != "plain" else ".txt"
            (out / f"{pid}_{platform}{ext}").write_text(
                result[platform], encoding="utf-8"
            )
    
    return result
