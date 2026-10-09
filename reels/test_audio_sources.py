import unittest
from unittest.mock import patch
import audio_sources as s
from audio_rights import validate_rights


class SourceTests(unittest.TestCase):
    def test_all_seven_providers_are_honestly_routed(self):
        rows = s.search_plan("soft wood", "sfx")["sources"]
        self.assertEqual(len(rows), 7)
        modes = {r["provider"]: r["mode"] for r in rows}
        self.assertEqual(modes["myinstants"], "reference_only")
        self.assertEqual(modes["youtube"], "account_required")
        self.assertFalse(any(r["status"] == "results" for r in rows))

    def test_mixkit_parser_and_real_download_not_preview(self):
        html = '''<div data-audio-player-item-id-value="12" data-audio-player-item-type-value="sfx">
        <h2 class="item-grid-card__title"> Soft &amp; short wood </h2>
        <button data-download--button-modal-url-value="/free-sound-effects/download/12/"></button></div>'''
        with patch.object(s, "get_page", return_value=html):
            result = s.mixkit_search("soft wood")
        self.assertEqual(result[0]["title"], "Soft & short wood")
        self.assertEqual(result[0]["match_score"], 2)
        with patch.object(s, "get_page", return_value='<div data-download--modal-url-value="https://assets.mixkit.co/active_storage/sfx/12/12.wav">'):
            item = s.mixkit_request(result[0])
        validate_rights(item)
        self.assertTrue(item["download_url"].endswith("12.wav"))
        with patch.object(s, "get_page", return_value='<audio src="preview.mp3">'):
            with self.assertRaises(ValueError):
                s.mixkit_request(result[0])

    def test_provider_license_cannot_be_applied_to_arbitrary_audio(self):
        item = {"kind": "sfx", "license": "Mixkit-SFX-Free", "source_url": "https://evil.test/",
                "license_url": "https://mixkit.co/license/modal/sfxFree/", "download_url": "https://assets.mixkit.co/a.wav",
                "usage": "facebook-commercial-video"}
        with self.assertRaises(ValueError):
            validate_rights(item)
        for lic in ("CC-BY-NC-4.0", "Uppbeat-Free", "YouTube", "unknown"):
            with self.assertRaises(ValueError):
                validate_rights(dict(item, license=lic))
        validate_rights({"license": "CC-BY-3.0", "attribution": "Artist credit"})

    def test_empty_changed_markup_does_not_fabricate_candidates(self):
        with patch.object(s, "get_page", return_value="<html>Sign in</html>"):
            self.assertEqual(s.mixkit_search("wood"), [])

    def test_wrong_material_does_not_win_on_action_word(self):
        html = ''.join(f'<div data-audio-player-item-id-value="{i}" data-audio-player-item-type-value="sfx"><h2 class="item-grid-card__title">{title}</h2><button data-download--button-modal-url-value="/free-sound-effects/download/{i}/"></button></div>'
                       for i, title in [(1, "Fish dropped hit"), (2, "Soft wood hit")])
        with patch.object(s, "get_page", return_value=html):
            results = s.mixkit_search("soft wood impact")
        self.assertEqual(results[0]["provider_id"], "2")
        self.assertLess(results[1]["match_score"], 2)
