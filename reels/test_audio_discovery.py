import unittest
from datetime import date
from unittest.mock import patch
import audio_discovery as a


class DiscoveryTests(unittest.TestCase):
    def test_freshness_region_rights_and_repeat(self):
        catalog = [{"id": i, "kind": "music", "license": "CC0-1.0", "tags": ["chill"]} for i in ("a", "b")]
        catalog.append({"id": "unlicensed", "kind": "music", "license": "unknown", "tags": ["chill"]})
        signal = {"title": "Observed recording", "platform": "tiktok", "region": "US", "observed_on": "2026-10-08",
                  "url": "https://example.org/chart", "evidence": "Test fixture only", "signal": "rising", "tags": ["chill"]}
        with patch.object(a.p, "asset_path"):
            result = a.rank(catalog, [signal, dict(signal, observed_on="2026-09-01"), dict(signal, region="VN")],
                            [{"music": "a"}], "US", date(2026, 10, 8))
        self.assertEqual(result["fresh_signals"], 1)
        self.assertEqual(len(result["rejected_observations"]), 2)
        self.assertEqual([c["id"] for c in result["candidates"]], ["b", "a"])
        self.assertTrue(all(c["trend_status"] == "style_match_only" for c in result["candidates"]))

    def test_no_evidence_never_claims_trending(self):
        with patch.object(a.p, "asset_path"):
            result = a.rank([{"id": "a", "kind": "music", "license": "CC0-1.0", "tags": ["chill"]}], [], [], "US")
        self.assertEqual(result["status"], "no_verified_trend_fallback")
        self.assertEqual(result["candidates"][0]["trend_status"], "licensed_fallback")

    def test_invalid_file_is_not_renderable(self):
        with patch.object(a.p, "asset_path", side_effect=ValueError("hash mismatch")):
            result = a.rank([{"id": "a", "kind": "sfx", "license": "CC0-1.0"}], [], [], "US")
        self.assertEqual(result["candidates"], [])
