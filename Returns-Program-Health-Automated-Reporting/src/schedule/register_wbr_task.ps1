# Register the weekly WBR refresh in Windows Task Scheduler (run once, as the report owner).
# Runs every Monday at 06:00, after the Sunday 23:59 data load, so the pre-read is ready by 08:00.
$repo = Resolve-Path "$PSScriptRoot\..\.."
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\src\schedule\run_wbr_weekly.ps1`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 6:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 60) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "Returns WBR weekly refresh" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Builds excel/Returns_WBR_<week>.xlsx and reports/WBR_<week>.pdf for the week that just ended"

# Equivalent one-liner with schtasks:
# schtasks /Create /TN "Returns WBR weekly refresh" /SC WEEKLY /D MON /ST 06:00 ^
#   /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\repo\src\schedule\run_wbr_weekly.ps1"
