# Reel v2: premium pilot and Flow cutaways

The pilot is `output/2026-10-08-luxury-shelving-v04`. Creative direction is warm,
rhythmic luxury using the actual branch shelving. All product/process imagery is
real. Google Flow is limited to atmosphere without products or people. No posting.

## Plan and render compatibility

`pipeline.py` still accepts v1 with its 720x1280/30 defaults. New plans use
`version: 2` and `render: {"width":1080,"height":1920,"fps":30}`. The other supported
profile is 720x1280/30 for draft review. Keep a copy of each draft before changing
profile; changed profile invalidates prepared scenes, outro and export approval.
OpenCut receives the exact profile from `prepared.json`. H.264/AAC output remains
mandatory. A 1080p file does not recover detail missing from 720p source clips.

Each v2 shot has `role`: hook, context, action, detail, payoff or atmosphere.
Optional `actions` entries have absolute `source_time` and a `label`.
Optional `source_crop` is a normalized x/y/width/height rectangle, applied before
cover/contain. Crop only to improve framing, never to imply a different product.
`transition_duration` controls a fade (0.1–0.5s), default 0.4s; cuts do not overlap.

Optional `effects` controls:

```json
{
  "reason": "Compress approach, return to real speed at contact",
  "speed_segments": [
    {"duration": 0.6, "from": 1, "to": 1.5},
    {"duration": 0.8, "from": 1.5, "to": 1.5},
    {"duration": 1.2, "from": 1.5, "to": 1}
  ],
  "motion": [
    {"time": 0, "zoom": 1, "x": 0.5, "y": 0.5},
    {"time": 2.6, "zoom": 1.04, "x": 0.52, "y": 0.48}
  ],
  "title_style": "luxury",
  "title_size": 38
}
```

Segment durations are output seconds, sum to shot duration, speeds 0.5–2 and
continuous across boundaries. Speed changes linearly within a segment; source
time integrates speed, while FFmpeg uses its inverse. No optical flow. The
minimum speed must have enough source fps for 30fps output. Do not combine
`speed` with `speed_segments`, or `push_in` with `motion`. Motion x/y are normalized
positions within available zoom overscan; motion cannot recover cropped edges.

`color` accepts brightness (-0.08–0.08), gamma (0.9–1.1), red/blue midtone balance
(-0.08–0.08). Contrast and saturation retain their old bounds. Inspect against
source; there is no automatic color-match or stabilization claim.

SFX can use an absolute `start`, or `shot` (zero-based) plus absolute `source_time`.
Validation computes the latter's `start` using the shared source/output clock,
including ramp and transition offsets. `music.gain` defaults to .24; `mix` accepts
duck_threshold, duck_ratio, duck_attack and duck_release. Source audio stays muted.

## Flow setup and bounded acquisition

Run `scripts/setup-flowkit.ps1`, then:

```powershell
powershell -File scripts/start-flowkit.ps1 -ProjectId <uuid> -Job output/<job>
.\.venv-reels\Scripts\python.exe reels/flowkit_adapter.py health --project-id <uuid> --job output/<job>
```

Load `integrations/flowkit/extension` through Chrome's Load unpacked control and
leave the signed-in Flow project open. No credentials are copied into this repo.
The server is pinned to `bc051f2308db050b0d987b696c843664d483b515` (extension 0.3.4),
the inspected pre-anti-hijack release. Do not auto-update the extension or vendor.
Normal provider challenges stop acquisition; use the Flow UI to resolve them.

`flow-requests.json` lists id, purpose="atmosphere", no_product_or_people=true and
prompt. The adapter uses the pinned direct Omni text-video endpoint, one 4s/720p
portrait output per submission. It deliberately does not use Flowkit's image,
batch auto-retry, review-regenerate, finalize or publishing workflows. Submit one
selected ID, then poll its persisted receipt:

```powershell
.\.venv-reels\Scripts\python.exe reels/flowkit_adapter.py submit --id leaf-light-01 --project-id <uuid> --job output/<job>
.\.venv-reels\Scripts\python.exe reels/flowkit_adapter.py poll --id leaf-light-01 --project-id <uuid> --job output/<job>
```

The provider guard reserves an attempt in `flow/budget.json` **before** submission,
across process restarts. Six reservations is a hard ceiling; failed/uncertain
submissions count conservatively. No cross-profile failover. Re-running the same
ID never resubmits. If no receipt returns, check the Flow project and reconcile
manually; never delete budget or unknown records to retry. No purchase/top-up.
Download failures can be retried by polling the same receipt without generation.

After visual inspection, a Flow media manifest entry must have origin=google_flow
and ai_review={visual:"pass",no_product_or_people:true}. Store the generation
provenance next to it. The pipeline allows at most two atmosphere clips totaling
two seconds; rejects unreviewed clips. All their audio is discarded.

Write `flow/<id>-review.json` with visual, no_product_or_people and specific notes,
then run the adapter's `import --id <id>` command with the same job/project
arguments. It verifies the downloaded hash, analyzes the media and registers its
origin/review/provenance into the main manifest. No automatic visual approval.

## Review and acceptance

Keep edit-plan, voice timing, original OpenCut export, final conform, timeline,
storyboard, source evidence and review together. Review the actual moving video
and sound on the local review page; contact sheets alone do not certify motion,
music choice, pronunciation or subjective polish. A technical pass alone stays
needs_review. Never claim guaranteed reach or label heuristic scores as retention.

Tests: `.venv-reels/Scripts/python.exe -m unittest discover -s reels` and
`bun test tests/schema.test.ts` in opencut-mcp. Enable `REELS_INTEGRATION=1` for the
sequential FFmpeg fixtures. Run render tests and production renders sequentially.
