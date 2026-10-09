import tempfile
import unittest
import wave
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import audio_download as d


class DownloadTests(unittest.TestCase):
    def request(self):
        return {"id": "test-chill", "kind": "music", "title": "Test", "author": "Fixture",
                "license": "CC0-1.0", "tags": ["chill"], "license_evidence": "Test fixture, not real rights evidence",
                "verified_on": datetime.now(timezone.utc).date().isoformat(),
                "source_url": "https://example.org/source", "license_url": "https://example.org/license",
                "download_url": "https://example.org/test.wav"}

    def test_download_validate_cache_and_preserve_catalog(self):
        def fetch(url, dest, **kwargs):
            if url.endswith(".wav"):
                with wave.open(str(dest), "wb") as f:
                    f.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                    f.writeframes(b"\0\0"*24000)
            else:
                Path(dest).write_bytes(b"fixture source/license snapshot")
        with tempfile.TemporaryDirectory() as tmp, patch.object(d.p, "LIBRARY", Path(tmp)), patch.object(d, "public_url"), patch.object(d, "fetch", side_effect=fetch) as network:
            d.p.write(Path(tmp)/"catalog.json", {"assets": [{"id": "existing"}]})
            result = d.acquire(self.request())
            self.assertEqual(result["status"], "downloaded")
            self.assertEqual(len(d.p.read(Path(tmp)/"catalog.json")["assets"]), 2)
            network.reset_mock()
            self.assertEqual(d.acquire(self.request())["status"], "cached")
            network.assert_not_called()
            with self.assertRaises(ValueError):
                d.acquire(dict(self.request(), download_url="https://example.org/other.wav"))

    def test_reject_invalid_requests(self):
        for change in ({"id": "../escape"}, {"license": "unknown"}, {"license_evidence": ""},
                       {"verified_on": "2020-01-01"}, {"license": "CC-BY-4.0"}):
            with self.assertRaises(ValueError):
                d.validate_request(dict(self.request(), **change))

    def test_reject_private_urls_and_redirects(self):
        for url in ("file:///secret", "http://example.org", "https://user:pass@example.org"):
            with self.assertRaises(ValueError):
                d.public_url(url)
        with patch.object(d.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                d.public_url("https://example.org/audio")
            with self.assertRaises(ValueError):
                d.SafeRedirect().redirect_request(None, None, 302, "", {}, "https://example.org/private")

    def test_invalid_payload_never_enters_catalog(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(d.p, "LIBRARY", Path(tmp)), patch.object(d, "public_url"), patch.object(d, "fetch", side_effect=lambda u, dest, **kw: Path(dest).write_bytes(b"<html>not audio</html>")):
            with self.assertRaises(RuntimeError):
                d.acquire(self.request())
            self.assertFalse((Path(tmp)/"catalog.json").exists())
            self.assertFalse((Path(tmp)/"downloaded/test-chill").exists())
