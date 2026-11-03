# Register (or refresh) the autonomous loop: an hourly turn plus a watchdog.
#
#   powershell -File scripts/ops/install_hourly_task.ps1
#   powershell -File scripts/ops/install_hourly_task.ps1 -Uninstall
#
# Why two tasks:
#   * HCS-OpenCode-Hourly  runs one OpenCode turn per hour.
#   * HCS-OpenCode-Watchdog runs every 15 minutes and restarts the turn when the
#     heartbeat is stale or the last turn failed. This also covers a missed hourly
#     run after sleep or a reboot, without needing elevation to register a task with
#     StartWhenAvailable.
#
# `schtasks` is used instead of `Register-ScheduledTask` because the latter needs
# elevation for an interactive principal on this machine; `schtasks` registers a
# user task without it, which is what a personal automation needs.
#
# The tasks do not bypass approvals beyond the explicit `--auto` flag in the wake-up
# script, and they never tag or publish.

param(
    [string]$HourlyTask = "HCS-OpenCode-Hourly",
    [string]$WatchdogTask = "HCS-OpenCode-Watchdog",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if ($Uninstall) {
    foreach ($name in @($HourlyTask, $WatchdogTask)) {
        schtasks /Delete /TN $name /F 2>$null | Out-Null
        Write-Output "removed $name"
    }
    exit 0
}

$wakeScript = Join-Path $PSScriptRoot "hourly_wakeup.ps1"
$watchScript = Join-Path $PSScriptRoot "watchdog.ps1"
foreach ($path in @($wakeScript, $watchScript)) {
    if (-not (Test-Path $path)) { throw "missing script: $path" }
}

$hourlyCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$wakeScript`" -RepoRoot `"$RepoRoot`""
$watchCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$watchScript`" -RepoRoot `"$RepoRoot`""

schtasks /Create /TN $HourlyTask /SC HOURLY /MO 1 /TR $hourlyCommand /F | Out-Null
Write-Output "registered $HourlyTask (hourly)"

schtasks /Create /TN $WatchdogTask /SC MINUTE /MO 15 /TR $watchCommand /F | Out-Null
Write-Output "registered $WatchdogTask (every 15 minutes)"

foreach ($name in @($HourlyTask, $WatchdogTask)) {
    $info = schtasks /Query /TN $name /FO LIST 2>$null
    $status = ($info | Select-String -Pattern "^Status:|^Nächste Laufzeit:|^Next Run Time:" | Select-Object -First 2) -join " | "
    Write-Output "$name -> $status"
}
Write-Output "logs: $RepoRoot\logs\hourly-wakeup.log, $RepoRoot\logs\watchdog.log, $RepoRoot\logs\heartbeat.json"
