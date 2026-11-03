# Watchdog for the hourly wake-up.
#
# The scheduled wake-up can be skipped or killed by a reboot, a sleeping machine or a
# crashed PowerShell host. This watchdog runs more often than the wake-up and only
# acts when the heartbeat is missing, stale, or reports a failure. It never starts a
# second turn while one is running (the wake-up script's PID lock decides that).
#
# Usage:
#   powershell -File scripts/ops/watchdog.ps1
#   powershell -File scripts/ops/watchdog.ps1 -DryRun
#   powershell -File scripts/ops/watchdog.ps1 -MaxAgeMinutes 75

param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$MaxAgeMinutes = 75,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "watchdog.log"
$heartbeatFile = Join-Path $logDir "heartbeat.json"
$wakeScript = Join-Path $PSScriptRoot "hourly_wakeup.ps1"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log([string]$Message) {
    Add-Content -Path $logFile -Value "$stamp  $Message" -Encoding utf8
}

$reason = $null
if (-not (Test-Path $heartbeatFile)) {
    $reason = "no heartbeat yet"
} else {
    try {
        $heartbeat = Get-Content $heartbeatFile -Raw | ConvertFrom-Json
        $updated = [datetime]$heartbeat.updatedAt
        $ageMinutes = ((Get-Date).ToUniversalTime() - $updated.ToUniversalTime()).TotalMinutes
        if ($ageMinutes -gt $MaxAgeMinutes) {
            $reason = "heartbeat is {0:N0} min old (limit {1})" -f $ageMinutes, $MaxAgeMinutes
        } elseif ($heartbeat.status -eq "failed") {
            $reason = "last run failed with exit code $($heartbeat.exitCode)"
        } elseif ($heartbeat.status -eq "running") {
            $runningFor = ((Get-Date).ToUniversalTime() - $updated.ToUniversalTime()).TotalMinutes
            if ($runningFor -gt $MaxAgeMinutes) {
                $reason = "a run has been marked running for {0:N0} min" -f $runningFor
            }
        }
    } catch {
        $reason = "heartbeat cannot be parsed"
    }
}

if ($null -eq $reason) {
    Write-Log "ok: heartbeat is current"
    exit 0
}

Write-Log "action: $reason"
if ($DryRun) {
    Write-Log "dry-run: would start $wakeScript"
    exit 0
}

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $wakeScript -RepoRoot $RepoRoot
    $exit = $LASTEXITCODE
    Write-Log "wake-up started by watchdog, exit=$exit"
    exit $exit
} catch {
    Write-Log "failed to start the wake-up: $($_.Exception.Message)"
    exit 1
}
