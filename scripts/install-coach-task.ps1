# Registers the weekly Augurai coach as a Windows scheduled task (Sundays, 10:00).
# Run once, from PowerShell, in the repository folder:  .\scripts\install-coach-task.ps1
# Remove later with:  Unregister-ScheduledTask -TaskName "Augurai Coach" -Confirm:$false

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv -ErrorAction Stop).Source

$action = New-ScheduledTaskAction -Execute $uv -Argument "run augurai coach" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 10:00
# StartWhenAvailable runs the task as soon as the PC is on if it was off at 10:00.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "Augurai Coach" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Weekly Augurai coach: reviews your Claude Code sessions and writes suggestions to coach/proposals." -Force | Out-Null

Write-Host "Registered 'Augurai Coach' for Sundays at 10:00 (repo: $repo)."
Write-Host "Review each week's suggestions with /coach-review in Claude Code (files are in $repo\coach\proposals)."
