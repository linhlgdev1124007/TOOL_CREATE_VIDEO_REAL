# Editorial direction for real-product Reels

Read before designing an edit. These are decision criteria, not a requirement to use every technique. The agent makes creative judgments from viewed footage; scripts do not autonomously understand scenes.

## Build a visual argument

Choose one promise supported by footage: an unusual silhouette, a satisfying fit, a surprising transformation, or a distinctive detail. The first shot must communicate that promise even without narration. A question must be answered by the film, not withheld behind a generic CTA.

Assign each shot a role in its `reason`: hook, context, action, detail, payoff. Reject a shot that adds neither new information nor a useful emotional pause. Prefer changing scale or viewpoint over repeating the same photo. Make the final reveal strong enough to repay the opening promise; if the only reveal has a cluttered background, state that limitation rather than synthesizing a different product.

## Continuity and rhythm

- Cut on a visible gesture/contact when the next shot continues its direction. Check frames immediately before/after the cut for discontinuity or a duplicated action.
- A cut between two almost identical framings can look accidental; choose a clearly different scale, a meaningful detail insert, or a different action moment.
- Use short shots for comprehension-friendly actions, longer shots when viewers must understand geometry or read text. Beat alignment is secondary to a readable action. Never claim beat synchronization without inspecting the actual audio timing.
- Reserve a dissolve for a time/pace change or calm reveal. Avoid dissolving over important hand contacts: overlapping limbs look like errors.
- Preserve space around a satisfying contact sound. Do not fill every moment with voice, music accents and whooshes simultaneously.

## Choose effects by purpose

| Need | Supported implementation | Reject when |
|---|---|---|
| Focus attention on a detail | `effects.push_in`, 1–1.12, smooth eased digital push | Product edges get cropped or source softness becomes visible |
| Compress a repetitive action | `effects.speed`, 1–2, constant visual speed; source audio muted | Contact becomes unreadable or changed movement misrepresents the process |
| Slow a clear action | `effects.speed`, 0.5–1, only enough source fps for 30fps output | Frames would need duplication or optical-flow invention |
| Reveal a caption at the relevant moment | Timed title with short opacity fade, top/bottom placement | Covers hands, exceeds readable exposure, or competes with the product |
| Match adjacent footage | Bounded contrast/saturation after side-by-side inspection | Creates a false wood color or crushes grain/shadows |

This is NOT variable speed ramping, object tracking, rotoscoping, masked depth text, stabilization or automatic color matching. Those require additional implementations and separate quality tests. Do not accept those effect names in plans or claim that ordinary zoom is 3D parallax. If requested, explain the missing capability explicitly.

## Sound design

Only three audio layers are permitted: voice, chill instrumental music and licensed SFX. Never use original workshop, camera, ambient, speech or outro audio. Music is ducked by speech; SFX have independent gains. Keep chill music under the visual outro with an ending fade. The final limiter does not prove a good balance.

Use licensed SFX for deliberate visual accents; never extract contact audio from the source. Added wood/air accents are editorial design, not documentary proof of an action. Avoid stacking an accent over every cut. Leave intentional gaps in narration. Listen for doubled contacts, intrusive background speech, harsh tools, abrupt ambience changes and music losing energy under long narration. If listening is unavailable, keep approval pending.

## Review before delivery

View selected-range samples, then rendered shots at native size and the final export. Compare opening clarity, action continuity, typography, product visibility and payoff. For retimed visuals place SFX at the new output-time contact; source audio remains absent. Inspect push-in endpoints for cropped branches. Check titles on a phone-sized view; larger type may require shorter lines.

Report evidence-based improvements and remaining defects, not a synthetic virality score. Actual audience retention requires a posted test; do not publish without permission. Preserve failed versions and keep creative correction rounds bounded by the main skill.
