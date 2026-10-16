import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import httpx
from .pdf import PaperError

ARXIV_ID = r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v[1-9]\d*)?"
CLASSIC_SOURCES = {
    "gpt-1": "https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf",
    "gpt-2": "https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf",
}


def download_classic(slug, path, max_bytes):
    if slug not in CLASSIC_SOURCES:
        raise PaperError("未知的经典论文来源。")
    with httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=False) as client:
        with client.stream("GET", CLASSIC_SOURCES[slug]) as response:
            response.raise_for_status()
            size = 0
            with path.open("wb") as output:
                for chunk in response.iter_bytes(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise PaperError("论文超过 30 MB 限制。")
                    output.write(chunk)
    return CLASSIC_SOURCES[slug]


def arxiv_id(value):
    value = value.strip()
    if re.fullmatch(ARXIV_ID, value):
        return value
    url = urlparse(value)
    if url.scheme != "https" or url.netloc != "arxiv.org" or url.query or url.fragment:
        raise PaperError("请输入 arxiv.org 的 HTTPS 摘要页、PDF 地址或论文编号。")
    match = re.fullmatch(r"/(?:abs|pdf)/(" + ARXIV_ID + r")(?:\.pdf)?", url.path)
    if not match:
        raise PaperError("无法识别 arXiv 论文编号。")
    return match.group(1)


def resolve_arxiv(identifier, client):
    if re.search(r"v\d+$", identifier):
        return identifier
    # Resolve once and persist the version before downloading; never follow arbitrary URLs.
    try:
        response = client.get("https://export.arxiv.org/api/query", params={"id_list": identifier})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        entry = root.find("{http://www.w3.org/2005/Atom}entry")
        source = entry.findtext("{http://www.w3.org/2005/Atom}id", "") if entry is not None else ""
        match = re.search(r"/(" + ARXIV_ID + r")$", source)
        if match and re.search(r"v\d+$", match.group(1)):
            return match.group(1)
    except (httpx.HTTPError, ET.ParseError):
        pass
    # Some networks cannot reach export.arxiv.org. The official abstract page
    # lists the versioned citation and submission history. Never guess a version.
    response = client.get("https://arxiv.org/abs/" + identifier)
    response.raise_for_status()
    versions = re.findall(re.escape(identifier) + r"v([1-9]\d*)", response.text)
    if not versions:
        raise PaperError("arXiv 暂未返回有效版本，请稍后重试。")
    return identifier + "v" + str(max(map(int, versions)))


def download_arxiv(identifier, path, max_bytes):
    with httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=False, headers={"User-Agent": "PaperLoop/1.0 (private paper reader)"}) as client:
        version = resolve_arxiv(identifier, client)
        url = "https://arxiv.org/pdf/" + version
        # Only follow redirects to known arXiv download hosts, checking every hop.
        for _ in range(4):
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    target = response.headers.get("location", "")
                    if target.startswith("/"):
                        target = "https://arxiv.org" + target
                    parsed = urlparse(target)
                    if parsed.scheme != "https" or parsed.netloc not in {"arxiv.org", "export.arxiv.org"} or not parsed.path.startswith("/pdf/"):
                        raise PaperError("论文下载发生了不支持的跳转。")
                    url = target
                    continue
                response.raise_for_status()
                size = 0
                with path.open("wb") as file:
                    for chunk in response.iter_bytes(65536):
                        size += len(chunk)
                        if size > max_bytes:
                            raise PaperError("论文超过 30 MB 限制。")
                        file.write(chunk)
                with path.open("rb") as file:
                    if not file.read(1024).lstrip().startswith(b"%PDF-"):
                        raise PaperError("arXiv 未返回 PDF，可能正受到限流，请稍后重试。")
                return version
        raise PaperError("论文下载跳转次数过多。")
