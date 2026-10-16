"""Server-only Supabase Storage; no privileged credentials reach the browser."""
import re
from urllib.parse import quote
import httpx


class StorageError(RuntimeError):
    pass


class Storage:
    def __init__(self, settings):
        self.settings = settings
        self.base = settings.supabase_url.rstrip("/") + "/storage/v1"
        self.headers = {"apikey": settings.storage_key}
        if not settings.storage_key.startswith("sb_secret_"):
            self.headers["Authorization"] = "Bearer " + settings.storage_key

    def path(self, identifier):
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise StorageError("无效的论文文件标识。")
        return quote(self.settings.storage_bucket) + "/" + identifier + ".pdf"

    def request(self, method, path, **kwargs):
        try:
            response = httpx.request(method, self.base + path, headers=self.headers, timeout=15, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise StorageError("私有文件存储暂时无法访问，请稍后重试。") from exc

    def exists(self, identifier):
        try:
            response = httpx.head(self.base + "/object/" + self.path(identifier), headers=self.headers, timeout=15)
            # Storage's HEAD endpoint uses 400 for missing objects on some versions.
            if response.status_code in {400, 404}:
                return False
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            raise StorageError("私有文件存储暂时无法访问，请稍后重试。") from exc

    def signed_upload(self, identifier):
        value = self.request("POST", "/object/upload/sign/" + self.path(identifier), json={}).json()
        return self.base + value["url"]

    def signed_download(self, identifier):
        value = self.request("POST", "/object/sign/" + self.path(identifier), json={"expiresIn": 60}).json()
        return self.base + value["signedURL"]

    def download(self, identifier, target):
        # Stream privately to a per-invocation scratch directory, enforcing the actual size.
        try:
            with httpx.stream("GET", self.base + "/object/" + self.path(identifier), headers=self.headers, timeout=90) as response:
                response.raise_for_status()
                size = 0
                with target.open("wb") as output:
                    for chunk in response.iter_bytes(65536):
                        size += len(chunk)
                        if size > self.settings.max_bytes:
                            raise StorageError("PDF 超过 30 MB 限制。")
                        output.write(chunk)
        except httpx.HTTPError as exc:
            target.unlink(missing_ok=True)
            raise StorageError("PDF 尚未上传完成或无法下载，请重新上传后重试。") from exc

    def upload(self, identifier, source):
        try:
            with source.open("rb") as content:
                response = httpx.post(self.base + "/object/" + self.path(identifier), content=content, headers={**self.headers, "Content-Type": "application/pdf", "x-upsert": "true"}, timeout=90)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError("PDF 保存失败，请重试导入。") from exc

    def remove(self, identifier):
        self.request("DELETE", "/object/" + quote(self.settings.storage_bucket), json={"prefixes": [identifier + ".pdf"]})
