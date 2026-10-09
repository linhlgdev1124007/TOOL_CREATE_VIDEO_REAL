import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import effects
import timing
import pipeline as p
import flowkit_adapter as flow


class TimingTests(unittest.TestCase):
    def ramp(self):
        return {"in": 10, "duration": 3, "effects": {"reason": "contact slows to real speed",
                "speed_segments": [{"duration": 1, "from": 1, "to": 2},
                                   {"duration": 2, "from": 2, "to": 1}]}}

    def test_ramp_roundtrip_and_contact(self):
        clip = self.ramp()
        effects.validate(clip, {"kind": "video", "fps": "30/1"})
        self.assertAlmostEqual(effects.source_duration(clip), 4.5)
        for t in (0, .1, .9, 1, 1.5, 2.9, 3):
            self.assertAlmostEqual(timing.output_at(clip, timing.source_at(clip, t)), t)
        timing.schedule([clip])
        self.assertAlmostEqual(timing.cue_time({"shot": 0, "source_time": 11.5}, [clip]), 1)
        with self.assertRaises(ValueError):
            timing.output_at(clip, 5)

    def test_invalid_ramp_and_motion(self):
        for changes in (
            {"speed_segments": [{"duration": 2, "from": 1, "to": 2}]},
            {"speed_segments": [{"duration": 3, "from": .5, "to": 1}]},
            {"motion": [{"time": 0, "zoom": 1, "x": .5, "y": .5},
                        {"time": 2, "zoom": 1.05, "x": .5, "y": .5}]}):
            clip = {"duration": 3, "effects": {"reason": "test", **changes}}
            with self.assertRaises(ValueError):
                effects.validate(clip, {"kind": "video", "fps": "30/1"})

    def test_v1_clock_and_transition(self):
        clips = [{"duration": 2}, {"duration": 3, "transition": "fade"}]
        self.assertAlmostEqual(timing.schedule(clips), 4.6)
        self.assertAlmostEqual(timing.source_at(clips[0], 1.5), 1.5)
        self.assertEqual(p.render_config({})["width"], 720)
        self.assertEqual(p.render_config({"render": {"width": 1080, "height": 1920, "fps": 30}})["width"], 1080)

    def test_real_ffmpeg_ramp_duration_and_motion_profiles(self):
        with tempfile.TemporaryDirectory(dir=p.ROOT/".tmp") as tmp:
            for width, height in ((720,1280), (1080,1920)):
                clip = self.ramp()
                clip["effects"]["motion"] = [
                    {"time": 0, "zoom": 1, "x": .45, "y": .5},
                    {"time": 3, "zoom": 1.04, "x": .55, "y": .5}]
                target = Path(tmp)/f"ramp-{width}.mp4"
                filt = timing.setpts(clip)+f",fps=30,scale={width}:{height}"
                filt += effects.motion_filter(clip, width, height)
                p.ff(["-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=4.6", "-vf", filt,
                      "-t", 3, "-an", "-c:v", "libx264", "-preset", "ultrafast", target])
                stream = p.probe(target)["streams"][0]
                self.assertEqual((stream["width"], stream["height"]), (width,height))
                self.assertEqual(int(stream["nb_frames"]), 90)

    def test_actual_render_contact_lands_at_shared_cue(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=p.ROOT/".tmp") as tmp:
            clip = self.ramp()
            target = Path(tmp)/"contact.mp4"
            # A source color change at 1.5s must land at output 1.0s, not 1.5s.
            filt = "drawbox=color=blue:t=fill:enable='gte(t,1.5)',"+timing.setpts(clip)+",fps=30"
            p.ff(["-f","lavfi","-i","color=red:s=64x64:r=30:d=4.6","-vf",filt,
                  "-t",3,"-c:v","libx264","-preset","ultrafast",target])
            for t, channel in ((.9,0),(1.1,2)):
                frame = Path(tmp)/f"{t}.png"
                p.ff(["-ss",t,"-i",target,"-frames:v",1,frame])
                with Image.open(frame) as im:
                    rgb = im.convert("RGB").getpixel((32,32))
                self.assertGreater(rgb[channel], 200)


class FlowTests(unittest.TestCase):
    def test_durable_limit_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"budget.json"
            for _ in range(6):
                flow.Budget(path).reserve({"rpc": "test"})
            with self.assertRaises(ValueError):
                flow.Budget(path).reserve({"rpc": "test"})
            self.assertEqual(len(p.read(path)["attempts"]), 6)

    def test_disconnect_never_submits(self):
        with patch.object(flow, "health", return_value={"ready": False}), patch.object(flow, "api") as api:
            with self.assertRaises(ValueError):
                flow.submit(Path("unused"), {}, "project")
            api.assert_not_called()

    def test_timeout_cannot_resubmit_same_cutaway(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = {"id": "leaf", "purpose": "atmosphere", "no_product_or_people": True, "prompt": "Leaf shadows"}
            with patch.object(flow, "health", return_value={"ready": True}), patch.object(flow, "api", side_effect=TimeoutError) as api:
                result = flow.submit(Path(tmp), item, "project")
                self.assertEqual(result["status"], "submission_unknown")
                with self.assertRaises(ValueError):
                    flow.submit(Path(tmp), item, "project")
                self.assertEqual(api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
