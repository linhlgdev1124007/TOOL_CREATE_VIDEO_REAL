import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline as p
import editorial
import effects


class PipelineTests(unittest.TestCase):
    def test_effects_reject_unsupported_and_unsafe_slow_motion(self):
        clip = {"duration": 2, "text": "DETAIL", "effects": {"speed": .5, "reason": "detail"}}
        with self.assertRaises(ValueError):
            effects.validate(clip, {"kind": "video", "fps": "30/1"})
        effects.validate(clip, {"kind": "video", "fps": "60/1"})
        self.assertEqual(effects.source_duration(clip), 1)
        for fx in ({"tracking": True}, {"speed": float("nan"), "reason": "bad"}, {"push_in": 1.1},
                   {"title_start": 1.9, "reason": "too brief"}):
            with self.assertRaises(ValueError):
                effects.validate(dict(clip, effects=fx), {"kind": "video", "fps": "60/1"})

    @classmethod
    def setUpClass(cls):
        (p.ROOT/".tmp").mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix="wrydeco-tests-", dir=p.ROOT/".tmp")
        cls.root = Path(cls.tmp.name)
        cls.source = cls.root/"source"
        cls.source.mkdir()
        cls.job = cls.root/"job"
        from PIL import Image
        Image.new("RGB", (800,600), "brown").save(cls.source/"wood.jpg")
        (cls.source/"corrupt.mp4").write_bytes(b"not a video")
        p.ff(["-f","lavfi","-i","color=c=tan:s=320x180:r=30:d=6","-an","-c:v","libx264",cls.source/"silent.mp4"])
        p.ff(["-f","lavfi","-i","color=c=white:s=180x320:r=30:d=2.7","-f","lavfi","-i","sine=frequency=440:duration=2.7", "-c:v","libx264","-c:a","aac",cls.root/"outro.mp4"])
        p.analyze(cls.source, cls.job)
        cls.manifest = p.read(cls.job/"media-manifest.json")
        cls.valid = {a["kind"]:a for a in cls.manifest["assets"] if a["status"] == "ok"}
        cls.lib = cls.root/"library"
        cls.lib.mkdir()
        p.ff(["-f","lavfi","-i","sine=frequency=200:duration=30",cls.lib/"music.wav"])
        p.ff(["-f","lavfi","-i","sine=frequency=100:duration=0.2",cls.lib/"sfx.wav"])
        p.write(cls.lib/"catalog.json", {"assets":[
            {"id":"music","kind":"music","file":"music.wav","license":"test-only","source_url":"test://fixture"},
            {"id":"sfx","kind":"sfx","file":"sfx.wav","license":"test-only","source_url":"test://fixture"}]})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def plan(self):
        return {"version":1,"story":"Visible fixture wood", "hooks":["a","b","c"],
                "outro":str(self.root/"outro.mp4"),
                "clips":[{"asset_id":self.valid[k]["id"],"in":0,"duration":5,"transition":t,
                          "reason":"test","evidence":"viewed test fixture"} for k,t in
                         [("image","cut"),("video","cut"),("image","fade")]],
                "narration":[{"start":.5,"text":"A wooden detail.","evidence":"test image"}],
                "music":{"id":"music"},
                "sfx":[{"id":"sfx","start":1,"reason":"test"},{"id":"sfx","start":10,"reason":"test"}]}

    def test_analysis_handles_image_silent_landscape_and_corrupt(self):
        self.assertEqual(len(self.manifest["assets"]),3)
        self.assertEqual(sum(a["status"] == "error" for a in self.manifest["assets"]),1)
        self.assertFalse(self.valid["video"]["has_audio"])
        self.assertTrue(Path(self.valid["image"]["storyboard"]).exists())
        self.assertGreater(len(self.valid["video"]["samples"]),1)

    def test_analysis_resume_preserves_cached_assets(self):
        p.analyze(self.source,self.job)
        again = p.read(self.job/"media-manifest.json")
        self.assertEqual({a["id"] for a in again["assets"]},{a["id"] for a in self.manifest["assets"]})

    def test_editorial_flags_repeated_photos_and_stalled_ending(self):
        plan = self.plan()
        manifest = {a["id"]: a for a in self.valid.values()}
        report = editorial.audit(plan, manifest)
        self.assertEqual(report["opening_kind"], "image")
        self.assertEqual(len(report["similar_photos"]), 1)
        self.assertEqual(report["longest_still_run"], 5)
        plan["clips"] = [plan["clips"][1], dict(plan["clips"][0], duration=3)]
        report = editorial.audit(plan, manifest)
        self.assertEqual(report["warnings"], [])

    def test_selected_range_inspection_includes_image_and_video(self):
        plan = self.plan()
        plan["clips"] = [dict(c, duration=.5) for c in plan["clips"][:2]]
        editorial.inspect(plan, {a["id"]: a for a in self.valid.values()}, self.job)
        self.assertTrue((self.job/"selected-shot-00.jpg").exists())
        self.assertTrue((self.job/"selected-shot-01.jpg").exists())

    def test_conform_removes_audio_tail_without_dropping_video_frames(self):
        target = self.root/"conformed.mp4"
        audio = self.root/"padded-audio.m4a"
        p.ff(["-i", self.lib/"music.wav", "-c:a", "aac", audio])
        p.conform_video(self.source/"silent.mp4", audio, target)
        streams = p.probe(target)["streams"]
        v = next(s for s in streams if s["codec_type"] == "video")
        a = next(s for s in streams if s["codec_type"] == "audio")
        self.assertEqual(int(v["nb_frames"]), 180)
        self.assertLessEqual(abs(float(v["duration"])-float(a["duration"])), .05)

    def test_transitions_compute_exact_schedule(self):
        plan = self.plan()
        with patch.object(p,"LIBRARY",self.lib):
            p.validate(plan,self.job)
        self.assertAlmostEqual(plan["content_duration"],14.6)
        self.assertAlmostEqual(plan["clips"][2]["timeline_start"],9.6)

    def test_v2_source_cue_tracks_ramp_and_transition(self):
        plan = self.plan()
        plan.update(version=2, render={"width":1080,"height":1920,"fps":30})
        for c in plan["clips"]:
            c["role"] = "detail"
        clip = plan["clips"][1]
        clip.update(duration=4, transition="fade", transition_duration=.2,
                    effects={"speed_segments":[{"duration":2,"from":1,"to":1.5},
                                               {"duration":2,"from":1.5,"to":1}],"reason":"test ramp"})
        plan["clips"][-1]["duration"] = 6
        plan["sfx"][0].update(shot=1,source_time=2.5)
        with patch.object(p,"LIBRARY",self.lib):
            p.validate(plan,self.job)
        self.assertAlmostEqual(plan["sfx"][0]["start"],6.8)
        self.assertAlmostEqual(plan["content_duration"],14.4)

    def test_profile_change_invalidates_export_before_opencut(self):
        plan = self.plan()
        plan.update(version=2,render={"width":720,"height":1280,"fps":30})
        for c in plan["clips"]:
            c["role"] = "detail"
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            job = Path(tmp)
            p.write(job/"media-manifest.json",self.manifest)
            with patch.object(p,"LIBRARY",self.lib):
                p.validate(plan,job)
                p.write(job/"prepared.json",{"plan_hash":p.digest(plan)})
                plan["render"] = {"width":1080,"height":1920,"fps":30}
                p.write(job/"edit-plan.json",plan)
                with self.assertRaisesRegex(ValueError,"Plan changed"):
                    p.export(job)

    def test_ai_cutaway_requires_review_and_two_second_cap(self):
        plan = self.plan()
        plan["version"] = 2
        for c in plan["clips"]:
            c["role"] = "detail"
        manifest = copy.deepcopy(self.manifest)
        for asset in manifest["assets"]:
            if asset["id"] == self.valid["video"]["id"]:
                asset.update(origin="google_flow",ai_review={"visual":"pass","no_product_or_people":True})
        plan["clips"][1].update(role="atmosphere",duration=2)
        plan["clips"][-1]["duration"] = 8
        with tempfile.TemporaryDirectory(dir=self.root) as tmp, patch.object(p,"LIBRARY",self.lib):
            job=Path(tmp)
            p.write(job/"media-manifest.json",manifest)
            p.validate(plan,job)
            plan["clips"][1]["duration"] = 2.1
            with self.assertRaisesRegex(ValueError,"AI cutaways"):
                p.validate(plan,job)
            plan["clips"][1].update(duration=2,role="payoff")
            with self.assertRaisesRegex(ValueError,"Flow cutaways"):
                p.validate(plan,job)

    def test_invalid_source_range_text_and_negative_time(self):
        for change in [lambda x:x["clips"][1].update({"in":3}),
                       lambda x:x["clips"][0].update({"text":"x"*29}),
                       lambda x:x["narration"][0].update({"start":-1}),
                       lambda x:x["clips"][0].update({"duration":float("nan")})]:
            plan = self.plan()
            change(plan)
            with patch.object(p,"LIBRARY",self.lib), self.assertRaises(ValueError):
                p.validate(plan,self.job)

    def test_unknown_rights_rejected(self):
        with patch.object(p,"LIBRARY",self.lib), self.assertRaises(ValueError):
            p.asset_path({"id":"x","file":"music.wav","source_url":"test://"})

    def test_audio_paths_cannot_escape_library(self):
        with patch.object(p,"LIBRARY",self.lib), self.assertRaises(ValueError):
            p.asset_path({"id":"x","file":"../outro.mp4","license":"test","source_url":"test://"})

    def test_changed_voice_schedule_rejected_before_render(self):
        plan = self.plan()
        with patch.object(p,"LIBRARY",self.lib):
            p.validate(plan,self.job)
        p.write(self.job/"voice-plan.json",{"key":"old"})
        with self.assertRaisesRegex(ValueError,"schedule changed"):
            p.prepare(plan,self.job,{})

    def test_missing_listening_never_becomes_complete(self):
        (self.job/"reel.mp4").write_bytes(b"review-only-fixture")
        p.write(self.job/"qa-report.json",{"checks":{"codec":True},"export_fingerprint":p.fingerprint(self.job/"reel.mp4")})
        p.write(self.job/"review.json",{"visual":"pass","listening":"unavailable","warnings_resolved":True,"notes":"Cannot hear"})
        result = p.review(self.job,self.job/"review.json")
        self.assertEqual(result["status"],"needs_review")

    def test_changed_export_invalidates_review(self):
        (self.job/"reel.mp4").write_bytes(b"changed")
        p.write(self.job/"review.json",{"visual":"pass","listening":"pass","notes":"test"})
        p.write(self.job/"qa-report.json",{"checks":{},"export_fingerprint":[]})
        with self.assertRaisesRegex(ValueError,"Export changed"):
            p.review(self.job,self.job/"review.json")

    @unittest.skipUnless(os.environ.get("REELS_INTEGRATION") == "1", "Enable sequential FFmpeg integration fixtures")
    def test_render_images_silent_video_and_loud_source(self):
        for mode in ("image", "silent", "loud"):
            job = self.root/(mode+"-job")
            job.mkdir(exist_ok=True)
            local_manifest = copy.deepcopy(self.manifest)
            plan = self.plan()
            plan["clips"][0].update(text="DETAIL", effects={"push_in": 1.06, "title_start": .3,
                                   "title_end": 3, "title_position": "bottom", "title_size": 36,
                                   "reason": "Test eased push and timed title"})
            if mode != "image":
                plan["clips"][1]["effects"] = {"speed": 1.2, "reason": "Test synchronized retiming"}
            if mode == "image":
                for clip in plan["clips"]:
                    clip["asset_id"] = self.valid["image"]["id"]
            if mode == "loud":
                hot = job/"hot-source.mp4"
                p.ff(["-i",self.source/"silent.mp4","-f","lavfi","-i","sine=frequency=650:duration=6",
                      "-af","volume=6","-c:v","copy","-c:a","aac",hot])
                noisy = copy.deepcopy(self.valid["video"])
                noisy.update(id="hot",path=str(hot),fingerprint=p.fingerprint(hot),has_audio=True)
                local_manifest["assets"].append(noisy)
                plan["clips"][1].update(asset_id="hot",sound_gain=.8)
            p.write(job/"media-manifest.json",local_manifest)
            with patch.object(p,"LIBRARY",self.lib):
                manifest = p.validate(plan,job)
                p.ff(["-f","lavfi","-i","sine=frequency=300:duration=0.4",job/"voice.wav"])
                p.write(job/"voice-timing.json",[{"start":.5,"end":.9,"file":str(job/"voice.wav")}])
                p.write(job/"voice-plan.json",{"key":p.digest([plan["narration"],plan["content_duration"],"Rye deco"])})
                with patch.object(p, "ff", wraps=p.ff) as calls:
                    p.prepare(plan,job,manifest)
                mix_args = next(c.args[0] for c in calls.call_args_list if c.args[0][-1] == job/"mix.wav")
                audio_inputs = [str(mix_args[i+1]) for i, arg in enumerate(mix_args[:-1]) if arg == "-i"]
                self.assertNotIn(str(plan["outro"]), audio_inputs)
                for asset in manifest.values():
                    self.assertNotIn(str(asset["path"]), audio_inputs)
                self.assertEqual(len(audio_inputs), 4)  # Voice, music, two SFX only.
                self.assertAlmostEqual(p.duration(job/"content.mp4"),plan["content_duration"],places=1)
                streams = p.probe(job/"outro-silent.mp4")["streams"]
                self.assertFalse(any(s["codec_type"] == "audio" for s in streams))
                audio = p.probe(job/"master.m4a")["streams"][0]
                self.assertEqual(audio["channels"],2)
                self.assertAlmostEqual(p.duration(job/"master.m4a"),plan["total_duration"],places=1)
                if mode == "loud":
                    import json
                    scan = p.ff(["-i",job/"master.m4a","-af","loudnorm=print_format=json","-f","null","-"]).stderr
                    measured = json.loads(scan[scan.rfind("{"):])
                    self.assertLessEqual(float(measured["input_tp"]),-1.5)


if __name__ == "__main__":
    unittest.main()
