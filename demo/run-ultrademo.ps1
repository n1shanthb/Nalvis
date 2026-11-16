param(
  [ValidateSet('doctor', 'capture', 'tts', 'timing', 'render', 'studio')]
  [string]$Step = 'doctor',
  [string]$Project = 'agentsuite-hackathon-2026-10-17-1200'
)
$ErrorActionPreference = 'Stop'
$workspace = Join-Path $PSScriptRoot 'ultrademo-workspace'
$toolRoot = Join-Path $PSScriptRoot 'video-tools/node_modules'
$env:PATH = (Join-Path $toolRoot 'ffmpeg-static') + ';' +
  (Join-Path $toolRoot 'ffprobe-static/bin/win32/x64') + ';' +
  (Join-Path $workspace '.venv/Scripts') + ';' + $env:PATH
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $env:USERPROFILE 'AppData/Local/ms-playwright'
$env:REMOTION_BROWSER_EXECUTABLE = Join-Path $env:PLAYWRIGHT_BROWSERS_PATH 'chromium-1228/chrome-win64/chrome.exe'
Push-Location $workspace
try {
  if ($Step -eq 'doctor') { & npm.cmd run doctor }
  elseif ($Step -eq 'timing') { & node "projects/$Project/fit-timing.mjs" }
  elseif ($Step -eq 'studio') { & npm.cmd run studio -- --public-dir "projects/$Project/assets" }
  else { & npm.cmd run $Step -- $Project }
  if ($LASTEXITCODE -ne 0) { throw "UltraDemo $Step failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
