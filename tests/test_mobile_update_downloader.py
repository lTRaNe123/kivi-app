import hashlib
import os
import tempfile
import unittest

from mobile_update_downloader import (
    DownloadCancelled,
    ProgressUiLimiter,
    stream_apk_to_file,
)


class FakeResponse:
    def __init__(self, url, payload, chunk_size):
        self.url = url
        self.headers = {"Content-Length": str(len(payload))}
        self._payload = payload
        self._chunk_size = chunk_size
        self.max_chunk_seen = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._payload = b""

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        size = min(chunk_size, self._chunk_size)
        for offset in range(0, len(self._payload), size):
            chunk = self._payload[offset:offset + size]
            self.max_chunk_seen = max(self.max_chunk_seen, len(chunk))
            yield chunk


class DownloaderTests(unittest.TestCase):
    def _payload(self, size):
        seed = b"vosk-update-stream-test-"
        return (seed * (size // len(seed) + 1))[:size]

    def test_streams_to_part_then_renames_after_success(self):
        payload = self._payload(22 * 1024 * 1024 + 123)
        expected_sha = hashlib.sha256(payload).hexdigest()
        responses = []
        progress_calls = []

        def fake_get(url, **_kwargs):
            resp = FakeResponse(url, payload, 512 * 1024)
            responses.append(resp)
            return resp

        with tempfile.TemporaryDirectory() as tmpdir:
            final_path = os.path.join(tmpdir, "vosk.apk")
            result = stream_apk_to_file(
                requests_get=fake_get,
                url="http://82.25.61.87/mobile-releases/android/test/vosk-test-2.apk",
                final_path=final_path,
                expected_size=len(payload),
                expected_sha256=expected_sha,
                max_size=200 * 1024 * 1024,
                allowed_hosts={"82.25.61.87"},
                cancel_requested=lambda: False,
                progress_callback=lambda total, content_length: progress_calls.append((total, content_length)),
            )

            self.assertEqual(result.path, final_path)
            self.assertTrue(os.path.exists(final_path))
            self.assertFalse(os.path.exists(final_path + ".part"))
            with open(final_path, "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), expected_sha)
            self.assertLessEqual(responses[0].max_chunk_seen, 512 * 1024)
            self.assertGreater(len(progress_calls), 1)

    def test_cancel_removes_part_file(self):
        payload = self._payload(4 * 1024 * 1024)
        expected_sha = hashlib.sha256(payload).hexdigest()
        calls = 0

        def fake_get(url, **_kwargs):
            return FakeResponse(url, payload, 512 * 1024)

        def cancel_after_first_chunk():
            nonlocal calls
            calls += 1
            return calls > 1

        with tempfile.TemporaryDirectory() as tmpdir:
            final_path = os.path.join(tmpdir, "vosk.apk")
            with self.assertRaises(DownloadCancelled):
                stream_apk_to_file(
                    requests_get=fake_get,
                    url="http://82.25.61.87/mobile-releases/android/test/vosk-test-2.apk",
                    final_path=final_path,
                    expected_size=len(payload),
                    expected_sha256=expected_sha,
                    max_size=200 * 1024 * 1024,
                    allowed_hosts={"82.25.61.87"},
                    cancel_requested=cancel_after_first_chunk,
                )
            self.assertFalse(os.path.exists(final_path))
            self.assertFalse(os.path.exists(final_path + ".part"))

    def test_progress_limiter_coalesces_fast_updates(self):
        limiter = ProgressUiLimiter(min_interval=0.2)
        emitted = 0
        total = 50 * 1024 * 1024
        now = 1000.0
        for downloaded in range(512 * 1024, total + 1, 512 * 1024):
            if limiter.should_emit(downloaded, total, now):
                emitted += 1
            now += 0.01

        self.assertLessEqual(emitted, 6)


if __name__ == "__main__":
    unittest.main()
