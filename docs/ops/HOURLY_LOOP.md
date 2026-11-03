# The autonomous hourly loop

Two Windows scheduled tasks keep this repository moving without a human in the
loop. They are deliberately boring: one runs a turn, one checks that the turn
actually ran.

## What runs

| Task | Schedule | Script | Purpose |
|---|---|---|---|
| `HCS-OpenCode-Hourly` | every hour | `scripts/ops/hourly_wakeup.ps1` | start one OpenCode turn for this session with a timestamped prompt |
| `HCS-OpenCode-Watchdog` | every 15 min | `scripts/ops/watchdog.ps1` | restart the turn if the heartbeat is stale or the last one failed |

Both are registered as the current user with `schtasks`, no elevation required.

## Why it cannot start twice

1. **OS-level check.** Before starting, the wake-up asks Windows whether an
   `opencode` process for this session already exists. A killed wrapper cannot make
   that answer stale.
2. **PID lock.** `logs/hourly-wakeup.lock` records the wrapper PID; a lock whose
   process is gone is recovered, a live one is respected.
3. **Task setting.** `schtasks` does not run the same task twice concurrently.

The first check is the important one: the OpenCode turn is a child process that can
outlive a killed PowerShell wrapper, so a file lock alone would be a false sense of
safety.

## Heartbeat, logs, repair

| File | Content |
|---|---|
| `logs/heartbeat.json` | last status (`running`, `success`, `failed`, `skipped`, `dry-run`), exit code, UTC timestamp |
| `logs/hourly-wakeup.log` | one line per decision and per attempt |
| `logs/hourly-wakeup.out.log` | stdout/stderr of the OpenCode turn |
| `logs/watchdog.log` | why the watchdog acted or did nothing |

Check the loop:

```powershell
schtasks /Query /TN HCS-OpenCode-Hourly /FO LIST
schtasks /Query /TN HCS-OpenCode-Watchdog /FO LIST
Get-Content logs/heartbeat.json
Get-Content logs/hourly-wakeup.log -Tail 20
Get-Content logs/watchdog.log -Tail 20
```

Dry-run both halves without starting a turn:

```powershell
powershell -File scripts/ops/hourly_wakeup.ps1 -DryRun
powershell -File scripts/ops/watchdog.ps1 -DryRun
```

Repair:

```powershell
# re-register both tasks (after moving the repo or updating the scripts)
powershell -File scripts/ops/install_hourly_task.ps1

# remove them
powershell -File scripts/ops/install_hourly_task.ps1 -Uninstall
```

If the machine was off for a while, the watchdog starts the turn as soon as it runs
again; the hourly task makes up a missed run too, unless the watchdog already did.

## Safety rules baked into the wake-up

- **Unmerged paths stop the run.** A repository in the middle of a conflict is not a
  place for an autonomous commit.
- **One retry, then a failed heartbeat.** A transient CLI failure gets a second
  attempt after a minute; a persistent one is recorded instead of looping forever.
- **No tag, no release, no deployment.** The prompt restates the owner-gated steps.
- **No secrets in logs.** The prompt and the scripts contain none, and the output log
  is the CLI's own output, not environment dumps.
