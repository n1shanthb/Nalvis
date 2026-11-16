# AgentSuite hackathon video

Requested: a two-minute hackathon video mixing product and technical explanation.
Script approved on 2026-10-17. English narration uses offline Piper; app footage uses the actual local HTTP-backed console.

## Production

Pipeline: UltraDemo, upstream commit `e7bdcfc241600b65bf6536f2c3c990a00a765b2d`.
Workspace: `E:\agentsuite\demo\ultrademo-workspace`.
Project: `projects/agentsuite-hackathon-2026-10-17-1200`.

Run from `E:\agentsuite` in PowerShell:

```powershell
.\demo\run-ultrademo.ps1 doctor
.\demo\run-ultrademo.ps1 capture
.\demo\run-ultrademo.ps1 tts
.\demo\run-ultrademo.ps1 timing
.\demo\run-ultrademo.ps1 render
python .\demo\ultrademo-workspace\projects\agentsuite-hackathon-2026-10-17-1200\verify.py
```

Capture is read-only and expects the existing app at `http://localhost:5173`, with its populated control plane. Do not replace its records with synthetic data. Re-capture rewrites the storyboard, so always run TTS and timing afterward. Original narration audio remains cached; timed WAV files are regenerated separately.

## Editorial decisions

- Preserve all approved narration. Shift a few scene boundaries to accommodate natural speech while retaining exactly 120 seconds overall.
- Show the actual GitHub PR review run from 2026-09-02, with its approval and validation history. This is a recorded workflow, not a newly triggered external action.
- Present React, FastAPI, Temporal, workers, PostgreSQL, Redis and connector relationships in a clearly labeled architecture graphic.
- Keep unsupported Slack automation visibly blocked.
- Mask visible email addresses in the captured DOM. Keep non-secret review IDs and evidence checks legible.
- Use a close-up for validation evidence, and top captions on Context Studio to leave the workspace cards visible.
- Visual review caught cropped labels in three initial camera moves. Their camera anchors were corrected in the source; `repair-framing.mjs` re-rendered those intervals and assembled them with the unchanged narration. A fresh full render uses the corrected storyboard directly.
- Do not claim a live crash-recovery demonstration, all connectors currently healthy, or a universal success rate.
- No changes to AgentSuite application behavior, policies, data, or external systems.

## Local compatibility adjustments

The UltraDemo checkout includes small Windows/Piper adaptations: invoke the Remotion CLI through Node rather than `execFileSync('npx')`; use the existing Chromium executable; remove Piper's obsolete synthesis `--download-dir` flag and download its model separately; support clip close-ups and per-scene caption placement. The source patch is preserved with the video source bundle.

## Review

Delivered MP4: `E:\agentsuite\demo\agentsuite-hackathon.mp4` (120.000 seconds, 1920×1080, 30 fps, H.264 + AAC, 20.7 MB). Full decode verification passed; all ten scene midpoint frames were visually inspected, including corrected framing. The approved narration is unchanged; timing boundaries were adjusted to fit exactly two minutes.

Scene review sheet: `E:\agentsuite\demo\agentsuite-scene-review.jpg`.

The first rendered cut is for user review as required by UltraDemo. Scene thumbnails and technical verification accompany the MP4. No public upload or external human-review service is required to watch it locally.
