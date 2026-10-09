# Edit-plan v1

Place `edit-plan.json` beside `media-manifest.json` in the job directory. Times are seconds. Select IDs from the manifest/catalog; sample filenames below illustrate fields, not usable assets.

```json
{
  "version": 1,
  "story": "The visible bench: sculptural base, fitting, final silhouette.",
  "hooks": ["Finished silhouette", "Close-up fitting", "Wood-grain reveal"],
  "outro": "D:/TOOL_CREATE_VIDEO_REAL/source/Wrydeco_real/video_outro/outro_wrydeo.mp4",
  "brand_pronunciation": "Rye deco",
  "clips": [
    {
      "asset_id": "manifest-id",
      "in": 0,
      "duration": 2,
      "crop_x": 0.5,
      "crop_y": 0.5,
      "transition": "cut",
      "text": "NATURE, SHAPED BY HAND",
      "contrast": 1.03,
      "saturation": 1.03,
      "sound_gain": 0,
      "reason": "Immediate view of the finished silhouette",
      "evidence": "Viewed frame at 0s: the complete bench is unobstructed"
    }
  ],
  "narration": [
    {"start": 0.4, "text": "Every curve tells a story.", "evidence": "Visible natural curves in the chosen hero image"}
  ],
  "music": {"id": "dream-culture", "in": 12},
  "sfx": [
    {"id": "catalog-sfx-id", "start": 1.9, "gain": 0.2, "reason": "Soft accent into the first workshop shot"}
  ],
  "caption": "Natural curves. A distinctive silhouette. Discover Wrydeco."
}
```

This abbreviated example requires additional clips/cues before validation: 3–12 shots, 2–4 SFX, total 15–30 seconds including actual outro duration. Aim 18–25 seconds. A fade on a shot overlaps its predecessor by 0.4s; pipeline computes `timeline_start`, `content_duration`, `outro_duration`, `total_duration`. Crop offsets range 0–1. Each line of overlay text is max 28 characters; max two lines; use short mobile-readable phrases.

`duration` is output duration. `in + duration * effects.speed` must fit video source. Image `in` is zero. No synthesized product imagery, replacement backgrounds or optical-flow slow motion. Source audio is always excluded, including the original outro. Legacy `sound_gain` is accepted but ignored; omit it or use zero. Select chill instrumental music long enough to cover the entire Reel, including the outro.

Optional per-clip effects (old plans remain valid):

```json
"effects": {
  "speed": 1.25,
  "push_in": 1.06,
  "title_start": 0.2,
  "title_end": 2.0,
  "title_position": "bottom",
  "title_size": 36,
  "reason": "Compress a repetitive approach, then draw attention to the unobstructed joint"
}
```

Use only needed fields. Speed 0.5–2 is constant, not a ramp. Slow motion requires source fps × speed ≥30; images cannot be retimed. Push-in 1–1.12 uses eased motion and is centered, so inspect product edges. Title times are local output seconds, exposure ≥0.7s; position top/bottom, size 28–40. Keep larger titles shorter and check actual rendered width. Unknown effects are rejected, including tracking/masking. Effects require a nonempty `reason`. Source-range inspection maps output times through speed.

`fit` defaults to `cover` (crop to portrait). Use `contain` for wide product reveals whose edges would otherwise be cut; it uses a dark matte and preserves the whole image.

Narration phrase starts are absolute timeline positions. The voice stage rejects overlapping phrases and speech ending less than 0.4s before outro. If start times change, rerun voice even when text is unchanged. For revisions rerun validate → voice → prepare → export → qa. Checkpoints reuse unchanged voice and scene files; each export creates a fresh editor project.

`prepared.json` is internal, not hand-edited. Both content and outro video supplied to OpenCut are silent. The master contains only generated voice, licensed chill music and licensed SFX. Original brand/outro audio is excluded. Old prepared mixes are invalidated by the audio-policy digest; rerun prepare and export.

Review file example:

```json
{
  "visual": "pass",
  "listening": "unavailable",
  "warnings_resolved": true,
  "notes": "Viewed final storyboard plus transition frames. Text and crop clear; brand fade is intentional. This environment cannot listen, so pronunciation and musical quality remain unapproved."
}
```

Only use `pass` after actually viewing/listening. Resolve detected black/silent regions individually (e.g. an intentional brand fade); do not automatically discard warnings. A `complete` result needs all technical checks, visual/listening passes and resolved warnings. `needs_review` is a valid honest delivery state, not a finished quality claim.
