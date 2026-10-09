# User-selected sound sources

Use these seven sources during sound discovery. They are not seven unrestricted download APIs. The skill performs web searches for public providers; `audio_sources.py` supplies consistent queries/statuses and has a live Mixkit SFX adapter. Preserve the user's no-source-audio policy.

## Search from the edit, not random popularity

Translate observed action into English search phrases: `soft wood impact`, `short fabric swish`, `subtle airy transition`, `warm chill acoustic instrumental`, `mellow lofi no vocals`. Use different searches for music and SFX. Avoid meme/siren/game effects unless the brief actually calls for them.

Run `reels/audio_sources.py --job <job> --kind sfx --query "soft wood impact" --live` to get public Mixkit results and routing queries for the other sources in `audio-source-search.json`. For music use `--kind music --query "warm mellow acoustic"`; this writes routing queries only, not fabricated results. Save each report under a distinct descriptive name before another search overwrites it.

The agent must then execute relevant public `query` values with its web search tool, open candidate pages, and record observations in `audio-provider-results.json`: provider, query, checked date, result URLs/titles, status (`results`, `no_results`, `blocked`, `login_required`, `reference_only`), rights evidence and relevance rationale. A generated query is NOT a completed search. Do not mark `not_searched` rows as success. Use the returned real download buttons, never guess CDN filenames or replace original downloads with preview files.

Search at least two suitable public providers for each music/SFX need when available. Keep at most five shortlisted recording candidates total per acquisition round. If blocked, record the reason and move to a permitted source; do not request user credentials merely because an alternative exists.

## Provider routing

| Source | Discovery and acquisition | Permission checks |
|---|---|---|
| Mixkit | Public SFX categories have a live search/resolver. `--live --download-limit 1` downloads up to one candidate scoring at least 2; weak matches are left for review, not downloaded automatically. Music is researched through web tools. | SFX uses `Mixkit-SFX-Free`, not CC0. Retain snapshots; only incorporate into finished videos. Do not redistribute downloaded stock with this tool/skill or templates. Music has different terms and is not covered by the SFX adapter. |
| Pixabay | Search public sound-effect/music pages with agent web tools. If an actual public download is available, pass it to the downloader; stop on a login/challenge. | `Pixabay-Content` needs exact-recording evidence, official source/download/license URLs and `usage: facebook-commercial-video`. Check third-party rights and any claim/certificate information. No promise of zero Content ID claims. |
| Chosic | Prioritize chill/ambient/acoustic music. Open individual track pages and download one track at a time. | Follow the track's own license/credit, not just the general “free” label. Supported CC0, CC-BY 3.0/4.0; skip NC/ND/SA or custom terms needing further implementation. |
| Freesound | Agent web search can locate public sound pages. Original downloads may require an authorized account; do not silently use a low-quality preview. | Check per-recording license and attribution. Skip NC/unsupported licenses. Do not automatically activate its API with a free token for this commercial workflow: API use has separate terms from recording rights. |
| YouTube Studio | Requires an authorized logged-in account. Register `login_required` without one; never scrape private Studio endpoints. | Check exact Audio Library license for Facebook use. A CC-BY recording can use the supported downloader only when its legitimate public file is available. Standard YouTube terms are not automatically converted to CC0. |
| Uppbeat | Public discovery via web tools; acquisition may need an account, quota and license for this business use. | Preserve exact project/license/credit requirements. Custom Uppbeat license is not supported by unattended downloader yet; mark pending, use a supported alternative. No purchase or subscription without approval. |
| Myinstants | Reference-only entry, disabled for automated site queries/downloads. | Its posted terms restrict automated queries and do not establish blanket commercial reuse rights. Do not label meme/movie/song extracts as royalty-free. Use a separately licensed sound with a similar editorial purpose instead. |

When a verified candidate supports unattended acquisition, write the request format from `audio-discovery.md`, including `provider`, `usage` for custom provider licenses, and exact credit. Run download + rank; check the report and listen before approving. Native Mixkit search ranks words/actions only, not perceptual sound quality. A download is not an editorial approval or a trend claim.

The downloaded folder is private working media for rendering, not a redistributable stock library. If packaging/publishing this project, exclude provider-restricted audio and snapshots with sensitive account data. Keep source media permanently muted, including the original outro.

Official references verified during integration:

- https://mixkit.co/license/modal/sfxFree/
- https://mixkit.co/license/modal/musicFree/
- https://pixabay.com/service/license-summary/
- https://www.chosic.com/free-music-policy/
- https://freesound.org/docs/api/terms_of_use.html
- https://support.google.com/youtube/answer/3376882
- https://uppbeat.io/help-center
- https://www.myinstants.com/en/terms_of_use.html

Recheck live terms when selecting new recordings; this reference does not replace per-track review.
