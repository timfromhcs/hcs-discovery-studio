# Hourly autonomous wake-up for this OpenCode session.
#
# Runs one OpenCode turn against the configured session with a timestamped prompt,
# under a lock so two runs can never overlap, and refuses to start while the
# repository has an unfinished merge. Everything is logged; nothing is hidden.
#
# Usage:
#   powershell -File scripts/ops/hourly_wakeup.ps1
#   powershell -File scripts/ops/hourly_wakeup.ps1 -DryRun
#
# Install (current user, hourly):
#   powershell -File scripts/ops/install_hourly_task.ps1

param(
    [string]$SessionId = "ses_e613840deffeSpQTz41k2XAc2i",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$LockMinutes = 55,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "hourly-wakeup.log"
$lockFile = Join-Path $logDir "hourly-wakeup.lock"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log([string]$Message) {
    $line = "$stamp  $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Output $line
}

if (Test-Path $lockFile) {
    $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($age.TotalMinutes -lt $LockMinutes) {
        Write-Log ("skip: previous run still active ({0:N0} min)" -f $age.TotalMinutes)
        exit 0
    }
    Write-Log ("stale lock ({0:N0} min) removed" -f $age.TotalMinutes)
    Remove-Item $lockFile -Force
}

Push-Location $RepoRoot
try {
    $unmerged = & git status --porcelain 2>$null | Where-Object { $_ -match "^(UU|AA|DD|AU|UA|DU|UD)" }
    if ($unmerged) {
        Write-Log "skip: repository has unmerged paths"
        exit 0
    }
    $dirty = (& git status --porcelain 2>$null | Measure-Object).Count
    $branch = (& git rev-parse --abbrev-ref HEAD 2>$null).Trim()
    Write-Log "branch=$branch dirty_files=$dirty"
} finally {
    Pop-Location
}

$time = Get-Date -Format "dddd HH:mm"
$prompt = @"
Hallo, es ist $time. Autonomer Weiterlauf des Plans in docs/engineering/PLAN_2026-11-03_ZERO_BACKEND.md.

Arbeite selbststaendig weiter:
1. Lies den Plan und docs/engineering/AGENT_LOG.md (letzter Eintrag), pruefe git status.
2. Nimm die naechste offene Phase, die ohne Rueckfrage machbar ist, und arbeite sie ab.
3. Verifiziere mit Tests/Gates; nichts als funktionierend melden, was nicht lief.
4. Aktualisiere AGENT_LOG, CHANGELOG und die Plan-Checkliste, committe (konventioneller Commit).
5. Ist der Plan fertig oder blockiert: kurz dokumentieren, nichts erfinden.

Keine Secrets ausgeben, keine Deployments ohne Not, keine Tags/Releases ohne Freigabe.
"@

New-Item -ItemType File -Path $lockFile -Force | Out-Null
try {
    $argv = @("--session", $SessionId, "--prompt", $prompt, "--auto", $RepoRoot)
    if ($DryRun) {
        Write-Log ("dry-run: opencode " + ($argv -join " ") )
        exit 0
    }
    Write-Log "starting opencode session $SessionId"
    $output = & opencode @argv 2>&1
    $exit = $LASTEXITCODE
    $output | Out-File -FilePath (Join-Path $logDir "hourly-wakeup.out.log") -Append -Encoding utf8
    Write-Log "finished: exit=$exit"
    exit $exit
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
