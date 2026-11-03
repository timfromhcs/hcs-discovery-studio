# Hourly autonomous wake-up for this OpenCode session.
#
# Design goals, in order:
#   1. never start twice at the same time  -> PID-aware lock, not an age-only timer
#   2. never fail silently                 -> heartbeat file + exit code in the log
#   3. recover from a failed turn          -> one retry after a short pause
#   4. be repairable by a human            -> one log file, one heartbeat, one switch
#
# Usage:
#   powershell -File scripts/ops/hourly_wakeup.ps1
#   powershell -File scripts/ops/hourly_wakeup.ps1 -DryRun
#
# The watchdog (scripts/ops/watchdog.ps1) restarts this when the heartbeat is stale.

param(
    [string]$SessionId = "ses_e613840deffeSpQTz41k2XAc2i",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$StaleHours = 3,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "hourly-wakeup.log"
$lockFile = Join-Path $logDir "hourly-wakeup.lock"
$heartbeatFile = Join-Path $logDir "heartbeat.json"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log([string]$Message) {
    $line = "$stamp  $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Output $line
}

function Read-Lock {
    if (-not (Test-Path $lockFile)) { return $null }
    try {
        return Get-Content $lockFile -Raw | ConvertFrom-Json
    } catch {
        return @{ pid = 0; startedAt = $stamp }
    }
}

function Test-LockHolderAlive($lock) {
    if ($null -eq $lock) { return $false }
    try {
        $process = Get-Process -Id ([int]$lock.pid) -ErrorAction Stop
        return $null -ne $process
    } catch {
        return $false
    }
}

# The file lock lives in the wrapper process, but the OpenCode turn is a separate
# process that survives a killed wrapper. Ask the OS whether a turn for this session
# is already running; that check cannot go stale.
function Get-RunningTurn {
    try {
        return Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -and
                $_.CommandLine -like "*--session*$SessionId*"
            } |
            Select-Object -First 1
    } catch {
        return $null
    }
}

function Write-Heartbeat([string]$Status, [int]$ExitCode, [string]$Detail) {
    $payload = [ordered]@{
        session   = $SessionId
        status    = $Status
        exitCode  = $ExitCode
        detail    = $Detail
        updatedAt = (Get-Date).ToUniversalTime().ToString("o")
    }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $heartbeatFile -Encoding utf8
}

$lock = Read-Lock
if ($null -ne $lock) {
    if (Test-LockHolderAlive $lock) {
        Write-Log ("skip: pid {0} is still running (started {1})" -f $lock.pid, $lock.startedAt)
        exit 0
    }
    $ageHours = 0
    try {
        $ageHours = ((Get-Date) - [datetime]$lock.startedAt).TotalHours
    } catch {
        $ageHours = 0
    }
    if ($ageHours -lt $StaleHours) {
        # The process is gone but the lock is recent: it may be a just-finished run
        # whose cleanup lost a race. Removing it immediately is safe because the
        # holder is provably not alive, but log it for the record.
        Write-Log ("recovering lock of a dead pid {0} ({1:N1} h old)" -f $lock.pid, $ageHours)
    } else {
        Write-Log ("removing stale lock of pid {0} ({1:N1} h old)" -f $lock.pid, $ageHours)
    }
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}

$runningTurn = Get-RunningTurn
if ($null -ne $runningTurn) {
    Write-Heartbeat "skipped" 0 "turn already running (pid $($runningTurn.ProcessId))"
    Write-Log ("skip: an opencode turn for this session is already running (pid {0})" -f $runningTurn.ProcessId)
    exit 0
}

Push-Location $RepoRoot
try {
    $unmerged = & git status --porcelain 2>$null | Where-Object { $_ -match "^(UU|AA|DD|AU|UA|DU|UD)" }
    if ($unmerged) {
        Write-Heartbeat "skipped" 0 "repository has unmerged paths"
        Write-Log "skip: repository has unmerged paths"
        exit 0
    }
    $dirty = (& git status --porcelain 2>$null | Measure-Object).Count
    $branch = (& git rev-parse --abbrev-ref HEAD 2>$null).Trim()
    Write-Log "branch=$branch dirty_files=$dirty"
} finally {
    Pop-Location
}

$opencode = Get-Command opencode -ErrorAction SilentlyContinue
if ($null -eq $opencode) {
    Write-Heartbeat "failed" 127 "opencode not found on PATH"
    Write-Log "failed: opencode is not on PATH; install it or fix the task environment"
    exit 127
}

$time = Get-Date -Format "dddd HH:mm"
$prompt = @"
Hallo, es ist $time. Autonomer Weiterlauf des Plans in docs/engineering/PLAN_2026-11-03_ZERO_BACKEND.md und docs/engineering/ROADMAP_LONG_TERM.md.

Arbeite selbststaendig weiter:
1. Lies den Plan und docs/engineering/AGENT_LOG.md (letzter Eintrag), pruefe git status.
2. Nimm die naechste offene Phase, die ohne Rueckfrage machbar ist, und arbeite sie ab.
3. Verifiziere mit Tests/Gates; nichts als funktionierend melden, was nicht lief.
4. Aktualisiere AGENT_LOG, CHANGELOG und die Plan-Checkliste, committe (konventioneller Commit).
5. Ist der Plan fertig oder blockiert: kurz dokumentieren, nichts erfinden.

Keine Secrets ausgeben, keine Deployments ohne Not, keine Tags/Releases ohne Freigabe.
"@

$lockPayload = [ordered]@{ pid = $PID; startedAt = $stamp; session = $SessionId }
$lockPayload | ConvertTo-Json | Set-Content -Path $lockFile -Encoding utf8

try {
    $argv = @("--session", $SessionId, "--prompt", $prompt, "--auto", $RepoRoot)
    if ($DryRun) {
        Write-Heartbeat "dry-run" 0 "would run opencode $SessionId"
        Write-Log ("dry-run: pid {0}, opencode at {1}" -f $PID, $opencode.Source)
        exit 0
    }
    $attempt = 0
    $exitCode = 1
    while ($attempt -lt 2 -and $exitCode -ne 0) {
        $attempt++
        Write-Heartbeat "running" 0 "attempt $attempt"
        Write-Log "starting opencode session $SessionId (attempt $attempt)"
        $output = & $opencode.Source @argv 2>&1
        $exitCode = $LASTEXITCODE
        $output | Out-File -FilePath (Join-Path $logDir "hourly-wakeup.out.log") -Append -Encoding utf8
        Write-Log "attempt $attempt finished: exit=$exitCode"
        if ($exitCode -ne 0 -and $attempt -lt 2) {
            Start-Sleep -Seconds 60
        }
    }
    if ($exitCode -eq 0) {
        Write-Heartbeat "success" 0 "opencode turn finished"
    } else {
        Write-Heartbeat "failed" $exitCode "opencode exited with $exitCode"
    }
    exit $exitCode
} finally {
    $current = Read-Lock
    if ($null -ne $current -and [int]$current.pid -eq $PID) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
    }
}
