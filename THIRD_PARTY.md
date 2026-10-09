# Third-party components

- OpenCut Classic: https://github.com/kenimo49/opencut-classic at the commit in
  `dependencies.lock.json`. Setup clones the original repository with its license.
- OpenCut MCP: https://github.com/kenimo49/opencut-mcp (MIT, Ken Imoto).
  Local modifications are distributed as a patch and source overlays under
  `patches/`; the original MIT license is preserved at `patches/OPENCUT-MCP-LICENSE`.
- Flowkit: https://github.com/crisng95/flowkit at the revision pinned in
  `scripts/setup-flowkit.ps1`. Optional separate download; retain upstream license.
- Kokoro ONNX runtime and model: installed/downloaded by setup. Model provenance
  is written to `.cache/kokoro/provenance.json`; consult original licenses.
- Audio is downloaded separately. Kenney assets use CC0; Kevin MacLeod starter
  music requires attribution. Generated `caption.txt` includes credits. Additional
  audio acquisitions must retain their own provenance and license evidence.

No source product footage, generated video, browser profile, access token, model
weights or downloaded audio library is bundled in this Git repository.
