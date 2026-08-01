import hashlib
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse


DEFAULT_CHUNK_SIZE = 512 * 1024
DEFAULT_FLUSH_INTERVAL = 4 * 1024 * 1024


class DownloadCancelled(Exception):
    pass


class DownloadVerificationError(ValueError):
    def __init__(self, message, *, label, stage):
        super().__init__(message)
        self.label = label
        self.stage = stage


@dataclass
class DownloadResult:
    path: str
    size: int
    sha256: str
    progress_calls: int


def normalize_sha256(value):
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text.split(":", 1)[1].strip()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise DownloadVerificationError(
            "SHA256 APK в ответе сервера имеет неверный формат",
            label="sha-verification-error",
            stage="sha-normalization",
        )
    return text


def stream_apk_to_file(
    *,
    requests_get,
    url,
    final_path,
    expected_size,
    expected_sha256,
    max_size,
    allowed_hosts,
    cancel_requested,
    progress_callback=None,
    chunk_size=DEFAULT_CHUNK_SIZE,
    flush_interval=DEFAULT_FLUSH_INTERVAL,
    replace_func=os.replace,
    open_file=open,
):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in allowed_hosts:
        raise ValueError("Хост обновления не разрешён")
    if expected_size and expected_size > max_size:
        raise ValueError("APK больше допустимого лимита 200 MB")
    normalized_expected_sha = normalize_sha256(expected_sha256)

    part_path = final_path + ".part"
    if os.path.exists(part_path):
        os.remove(part_path)

    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    total = 0
    progress_calls = 0
    bytes_since_flush = 0
    sha = hashlib.sha256()

    try:
        with requests_get(url, stream=True, timeout=(8, 30), allow_redirects=True) as resp:
            resp.raise_for_status()
            final_host = urlparse(getattr(resp, "url", url)).hostname
            if final_host not in allowed_hosts:
                raise ValueError("Редирект APK ведёт на неразрешённый хост")
            content_length = int(resp.headers.get("Content-Length") or expected_size or 0)
            if content_length and content_length > max_size:
                raise ValueError("APK больше допустимого лимита 200 MB")

            with open_file(part_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if cancel_requested():
                        raise DownloadCancelled("Загрузка отменена")
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_size:
                        raise ValueError("APK больше допустимого лимита 200 MB")
                    sha.update(chunk)
                    fh.write(chunk)
                    bytes_since_flush += len(chunk)
                    if bytes_since_flush >= flush_interval:
                        fh.flush()
                        bytes_since_flush = 0
                    if progress_callback:
                        progress_calls += 1
                        try:
                            progress_callback(total, content_length)
                        except Exception:
                            pass
                    chunk = None
                fh.flush()
    except Exception:
        try:
            os.remove(part_path)
        except OSError:
            pass
        raise

    if expected_size and total != expected_size:
        raise DownloadVerificationError(
            "Размер APK не совпадает с данными сервера",
            label="size-verification-error",
            stage="size-verification",
        )

    actual_sha = sha.hexdigest().lower()
    if actual_sha != normalized_expected_sha:
        raise DownloadVerificationError(
            "SHA256 APK не совпадает",
            label="sha-verification-error",
            stage="sha-verification",
        )

    try:
        replace_func(part_path, final_path)
    except Exception as exc:
        raise DownloadVerificationError(
            "Не удалось завершить файл APK",
            label="finalize-error",
            stage="finalize",
        ) from exc
    return DownloadResult(final_path, total, actual_sha, progress_calls)


class ProgressUiLimiter:
    def __init__(self, min_interval=0.2):
        self.min_interval = min_interval
        self.last_emit_at = None
        self.last_percent = None
        self.ui_updates = 0

    def should_emit(self, downloaded, content_length, now):
        if not content_length:
            percent = 0
        else:
            percent = max(0, min(100, int(downloaded * 100 / content_length)))
        if percent == self.last_percent and percent != 100:
            return False
        if self.last_emit_at is not None and percent != 100:
            if now - self.last_emit_at < self.min_interval:
                return False
        self.last_percent = percent
        self.last_emit_at = now
        self.ui_updates += 1
        return True
