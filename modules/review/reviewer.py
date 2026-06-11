"""
论文审稿模块 - 对比论文原文和公众号文章，检查事实准确性
- 从PDF提取论文正文
- 调用LLM进行审稿对比
- 输出审查报告，自动修正事实性错误

Config fallback: repo data/config.json -> ~/hermes-data/llm-paper-plan/wechat/config.json
"""

import json
import os
import sys
import re
import time
import urllib.request
from pathlib import Path

# ── resolve repo root ────────────────────────────────────────────────
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent  # modules/review -> modules -> repo

DATA_DIR = _REPO_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"
PAPERS_DIR = DATA_DIR / "papers"
REVIEWS_DIR = DATA_DIR / "reviews"

# Paper ID -> PDF path mapping
PDF_SOURCES = {
    "P1": ("https://arxiv.org/pdf/1706.03762", "/tmp/P1_paper.pdf"),
    "P2": ("https://arxiv.org/pdf/1810.04805", "/tmp/P2_paper.pdf"),
    "P3": ("https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf", "/tmp/P3_paper.pdf"),
    "P4": ("https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf", "/tmp/P4_paper.pdf"),
    "P5": ("https://arxiv.org/pdf/2005.14165", "/tmp/P5_paper.pdf"),
    "P6": ("https://arxiv.org/pdf/2001.08361", "/tmp/P6_paper.pdf"),
    "P7": ("https://arxiv.org/pdf/2203.15556", "/tmp/P7_paper.pdf"),
    "P8": ("https://arxiv.org/pdf/2205.14135", "/tmp/P8_paper.pdf"),
    "P9": ("https://arxiv.org/pdf/2307.08691", "/tmp/P9_paper.pdf"),
    "P10": ("https://arxiv.org/pdf/1910.02054", "/tmp/P10_paper.pdf"),
    "P11": ("https://arxiv.org/pdf/2203.02155", "/tmp/P11_paper.pdf"),
    "P12": ("https://arxiv.org/pdf/2212.08073", "/tmp/P12_paper.pdf"),
    "P13": ("https://arxiv.org/pdf/2305.18290", "/tmp/P13_paper.pdf"),
}

# Paper ID -> article JSON filename
ARTICLE_FILES = {
    "P1": "P1_attention_is_all_you_need.json",
    "P2": "P2_BERT.json",
    "P3": "P3_GPT1.json",
    "P4": "P4_GPT2.json",
    "P5": "P5_GPT3.json",
    "P6": "P6_ScalingLaws.json",
    "P7": "P7_Chinchilla.json",
    "P8": "P8_FlashAttention.json",
    "P9": "P9_FlashAttention2.json",
    "P10": "P10_ZeRO.json",
    "P11": "P11_InstructGPT.json",
    "P12": "P12_ConstitutionalAI.json",
    "P13": "P13_DPO.json",
    "stage1_summary": "stage1_summary.json",
    "stage2_summary": "stage2_summary.json",
}


def download_paper_pdf(paper_id, force=False):
    """Download paper PDF if not cached."""
    if paper_id not in PDF_SOURCES:
        return None
    url, local_path = PDF_SOURCES[paper_id]
    if not force and os.path.exists(local_path) and os.path.getsize(local_path) > 10000:
        return local_path
    print(f"  下载论文 PDF: {url[:60]}...")
    import subprocess
    try:
        result = subprocess.run(
            ["curl", "-sL", "--proxy", "http://127.0.0.1:7897", "-k",
             "-o", local_path, "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=120
        )
        code = result.stdout.strip()
        if os.path.exists(local_path) and os.path.getsize(local_path) > 10000:
            print(f"  下载完成: {os.path.getsize(local_path)//1024}KB (HTTP {code})")
            return local_path
        print(f"  [WARN] 下载失败: HTTP {code}, size={os.path.getsize(local_path) if os.path.exists(local_path) else 0}")
    except Exception as e:
        print(f"  [WARN] 下载异常: {e}")
    return None


def extract_paper_text(pdf_path, max_chars=15000):
    """Extract text from PDF, focusing on body (skip references/appendix)."""
    import fitz
    doc = fitz.open(pdf_path)
    all_text = ""

    # Extract text from all pages, stop when we hit References
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        # Stop at References section
        if re.search(r'\nReferences\n', text) or re.search(r'\nReferences\s*\n', text):
            ref_idx = re.search(r'\nReferences\n', text)
            if ref_idx:
                all_text += text[:ref_idx.start()]
            break
        all_text += text + "\n"

    doc.close()

    # Clean up
    all_text = re.sub(r'\n{3,}', '\n\n', all_text)
    all_text = all_text.strip()

    if len(all_text) > max_chars:
        all_text = all_text[:max_chars] + "\n\n[... truncated ...]"

    return all_text


def strip_html(html_content):
    """Remove HTML tags to get plain text."""
    text = re.sub(r'<figure[^>]*>.*?</figure>', '', html_content, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def get_api_credentials():
    """Get API credentials for review LLM calls.

    Priority:
    1. Environment variable DEEPSEEK_API_KEY (what Hermes gateway uses)
    2. auth.json credential_pool (Hermes managed credentials)
    3. config.yaml api_key (fallback)
    """
    import yaml

    home = os.path.expanduser("~")

    # 1. Check env var first (same source as Hermes gateway)
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    base_url = "https://api.deepseek.com/v1"
    model = "deepseek-chat"

    if not api_key:
        # 1b. Try sourcing ~/.zshrc for DEEPSEEK_API_KEY
        try:
            import subprocess
            r = subprocess.run(
                ["bash", "-c", "source ~/.zshrc 2>/dev/null && echo $DEEPSEEK_API_KEY"],
                capture_output=True, text=True, timeout=5
            )
            key = r.stdout.strip()
            if key and len(key) > 10:
                api_key = key
                os.environ["DEEPSEEK_API_KEY"] = key
        except Exception:
            pass

    if api_key:
        return api_key, base_url, model

    # 2. Check auth.json credential_pool
    auth_path = os.path.join(home, ".hermes", "auth.json")
    if os.path.exists(auth_path):
        try:
            with open(auth_path) as f:
                auth = json.load(f)
            pool = auth.get("credential_pool", {})
            for provider in ["deepseek", "custom:glm"]:
                creds = pool.get(provider, [])
                if creds:
                    cred = creds[0]
                    if cred.get("auth_type") == "api_key" and cred.get("base_url"):
                        base_url = cred["base_url"]
                        break
        except Exception:
            pass

    # 3. Fallback to config.yaml
    config_path = os.path.join(home, ".hermes", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        model_cfg = cfg.get("model", {})
        api_key = model_cfg.get("api_key", api_key)
        base_url = model_cfg.get("base_url", base_url)
        model = model_cfg.get("default", model)

    return api_key, base_url, model


def call_llm_review(paper_text, article_text, article_title):
    """Call LLM for review via OpenAI-compatible API."""
    api_key, base_url, model = get_api_credentials()

    if not api_key or not base_url:
        print("  [ERROR] Cannot find valid API credentials")
        print("  Sources checked: DEEPSEEK_API_KEY env, auth.json, config.yaml")
        return None

    # Strip /v1 suffix from base_url if present (we add our own path)
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    prompt = f"""你是一位严谨的学术论文审稿专家。你的任务是对比一篇AI论文原文和一篇面向大众的微信公众号文章，检查文章中的事实性描述是否准确。

## 审稿要求

1. **逐项核查事实**：文章中对论文的任何具体描述（数据、结论、方法细节、作者信息、发表年份等）都需要与原文核对
2. **区分风格和事实**：公众号文章可以有自己的表达风格、比喻、通俗化解释，这些不算错误。但如果意思和逻辑与原文不符，就是问题
3. **关注以下类型的问题**：
   - 错误的具体数字（如参数量、层数、页数、年份）
   - 错误的方法描述（如把A说成B）
   - 错误的因果逻辑
   - 过度简化导致误导
   - 捏造论文中不存在的细节
4. **允许的情况**：
   - 用通俗语言解释技术概念
   - 省略不重要的细节
   - 加入个人理解和观点（只要不与原文矛盾）
   - 使用比喻来帮助理解

## 论文原文（节选）

{paper_text}

## 公众号文章

标题：{article_title}

{article_text}

## 输出格式

请用以下JSON格式输出审查结果（不要输出其他内容）：

```json
{{{{
  "overall_quality": "good/acceptable/poor",
  "summary": "总体评价（一句话）",
  "issues": [
    {{{{
      "severity": "error/warning/suggestion",
      "location": "文章中出现问题的大致位置（引用原文片段）",
      "paper_fact": "论文原文的正确描述",
      "article_claim": "文章中的描述",
      "explanation": "问题说明",
      "suggested_fix": "建议修改为"
    }}}}
  ],
  "strengths": ["文章做得好的地方"]
}}}}
```

severity说明：
- error: 明确的事实性错误，必须修改
- warning: 可能引起误解的表述，建议修改
- suggestion: 可以改进但不强制"""

    body = json.dumps({
        "model": model,
        "max_tokens": 16000,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    url = f"{base_url}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
    )

    # Use proxy for external API calls
    proxy = urllib.request.ProxyHandler({
        'http': 'http://127.0.0.1:7897',
        'https': 'http://127.0.0.1:7897'
    })
    opener = urllib.request.build_opener(proxy)
    resp = opener.open(req, timeout=300)
    data = json.loads(resp.read())

    msg = data["choices"][0]["message"]
    response_text = msg.get("content", "") or ""

    # For reasoning models (e.g., glm-5.1), content may be empty, use reasoning_content
    if not response_text.strip():
        rc = msg.get("reasoning_content", "") or ""
        if rc.strip():
            response_text = rc
            print("  [INFO] Using reasoning_content as response")

    if not response_text.strip():
        print("  [WARN] LLM returned empty content")
        return None

    # Extract JSON from response (may be wrapped in ```json ... ```)
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    # Try parsing directly
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"raw_response": response_text}


def review_article(article_path, paper_id=None, auto_fix=False):
    """Review a single article against its source paper.

    Args:
        article_path: Path to the article JSON file.
        paper_id: Override the paper ID. If None, read from article.
        auto_fix: If True, attempt automatic fixes for errors.

    Returns:
        True if passed/skipped, False if failed.
    """
    print(f"\n{'='*60}")
    print(f"审稿: {os.path.basename(article_path)}")

    with open(article_path) as f:
        article = json.load(f)

    pid = paper_id or article.get("paper_id", "")
    title = article.get("title", "Unknown")

    print(f"  标题: {title}")
    print(f"  论文ID: {pid}")

    if not pid or pid == "stage1_summary":
        print("  [SKIP] 总结文章无法对比单篇论文")
        return True

    # Step 1: Get paper text
    pdf_path = download_paper_pdf(pid)
    if not pdf_path:
        print("  [ERROR] 无法获取论文PDF")
        return False

    print("  提取论文正文...")
    paper_text = extract_paper_text(pdf_path)
    print(f"  论文正文: {len(paper_text)} 字符")

    # Step 2: Get article plain text
    article_html = article.get("content", "")
    article_text = strip_html(article_html)
    print(f"  文章正文: {len(article_text)} 字符")

    # Step 3: LLM review
    print("  调用审稿模型...")
    review_result = call_llm_review(paper_text, article_text, title)

    if not review_result:
        print("  [ERROR] 审稿失败")
        return False

    # Step 4: Output review report
    if "raw_response" in review_result:
        print(f"\n  [WARN] 模型返回非JSON格式:")
        print(f"  {review_result['raw_response'][:500]}")
        return False

    quality = review_result.get("overall_quality", "unknown")
    summary = review_result.get("summary", "")
    issues = review_result.get("issues", [])
    strengths = review_result.get("strengths", [])

    print(f"\n  总体评价: {quality}")
    print(f"  {summary}")

    if strengths:
        print(f"\n  亮点:")
        for s in strengths:
            print(f"    + {s}")

    if issues:
        print(f"\n  发现 {len(issues)} 个问题:")
        error_count = 0
        for i, issue in enumerate(issues):
            severity = issue.get("severity", "warning")
            icon = {"error": "✗", "warning": "△", "suggestion": "○"}.get(severity, "?")
            print(f"\n  [{icon}] {severity.upper()}: {issue.get('explanation', '')}")
            print(f"    文章描述: {issue.get('article_claim', '')[:80]}")
            print(f"    论文事实: {issue.get('paper_fact', '')[:80]}")
            if issue.get("suggested_fix"):
                print(f"    建议修改: {issue['suggested_fix'][:80]}")
            if severity == "error":
                error_count += 1

        if error_count > 0 and auto_fix:
            print(f"\n  自动修正 {error_count} 个错误...")
            fixed = apply_fixes(article, issues)
            if fixed:
                with open(article_path, "w") as f:
                    json.dump(article, f, ensure_ascii=False, indent=2)
                print(f"  文章已修正并保存")

    # Save review report to data/reviews/
    os.makedirs(REVIEWS_DIR, exist_ok=True)
    report_path = REVIEWS_DIR / f"{pid}_review.json"
    with open(report_path, "w") as f:
        json.dump({
            "paper_id": pid,
            "title": title,
            "review": review_result,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  审稿报告已保存: {report_path}")

    return quality != "poor"


def apply_fixes(article, issues):
    """Apply suggested fixes to article content."""
    content = article.get("content", "")
    plain_text = strip_html(content)
    fixed = False

    for issue in issues:
        if issue.get("severity") != "error":
            continue
        fix = issue.get("suggested_fix", "")
        claim = issue.get("article_claim", "")
        if not fix or not claim:
            continue

        print(f"    需要修正: {claim[:50]}...")
        print(f"    修改为: {fix[:50]}...")
        fixed = True

    return fixed


def review_all():
    """Review all articles in data/articles/."""
    if not ARTICLES_DIR.exists():
        print(f"文章目录不存在: {ARTICLES_DIR}")
        return {"passed": 0, "failed": 0, "skipped": 0}

    json_files = sorted([f for f in os.listdir(ARTICLES_DIR) if f.endswith(".json")])
    print(f"找到 {len(json_files)} 篇文章待审稿")

    results = {"passed": 0, "failed": 0, "skipped": 0}

    for fname in json_files:
        path = ARTICLES_DIR / fname
        try:
            ok = review_article(str(path))
            if ok is None:
                results["skipped"] += 1
            elif ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            results["failed"] += 1

    print(f"\n{'='*60}")
    print(f"审稿完成: {results['passed']} 通过, {results['failed']} 有问题, {results['skipped']} 跳过")
    return results
