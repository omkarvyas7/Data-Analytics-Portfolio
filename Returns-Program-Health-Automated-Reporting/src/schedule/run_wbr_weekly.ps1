# Weekly WBR refresh wrapper (called by Windows Task Scheduler every Monday 06:00).
# Computes last week's Monday, rebuilds the database from the latest raw files, runs the WBR,
# logs output, and exits non-zero on failure so the task shows "Last Run Result" != 0.
param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\.."),
    [string]$Python = "$RepoRoot\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
$today = Get-Date
$daysSinceMonday = ([int]$today.DayOfWeek + 6) % 7
$week = $today.AddDays(-$daysSinceMonday - 7).ToString("yyyy-MM-dd")   # Monday of the week that just ended
$logDir = Join-Path $RepoRoot "reports\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "wbr_$week.log"

& $Python "$RepoRoot\src\run_wbr.py" --week $week --rebuild *>> $log
if ($LASTEXITCODE -ne 0) {
    Add-Content $log "FAILED with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Add-Content $log "OK: excel\Returns_WBR_$week.xlsx and reports\WBR_$week.pdf published"
