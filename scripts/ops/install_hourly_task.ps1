# Register (or refresh) the hourly autonomous wake-up for this OpenCode session.
#
#   powershell -File scripts/ops/install_hourly_task.ps1
#   powershell -File scripts/ops/install_hourly_task.ps1 -Uninstall
#
# The task runs as the current user, every hour, and writes to logs/hourly-wakeup.log.
# It is removable with the -Uninstall switch or `schtasks /Delete /TN HCS-OpenCode-Hourly /F`.

param(
    [string]$TaskName = "HCS-OpenCode-Hourly",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "hourly_wakeup.ps1"

if ($Uninstall) {
    schtasks /Delete /TN $TaskName /F | Out-Null
    Write-Output "removed scheduled task $TaskName"
    exit 0
}

if (-not (Test-Path $script)) {
    throw "hourly_wakeup.ps1 not found next to this script"
}

$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""
schtasks /Create /TN $TaskName /SC HOURLY /MO 1 /TR $action /F | Out-Null
schtasks /Query /TN $TaskName /FO LIST | Select-String -Pattern "TaskName|Status|Next Run|Task To Run"
Write-Output "installed $TaskName (hourly). Log: logs/hourly-wakeup.log"
