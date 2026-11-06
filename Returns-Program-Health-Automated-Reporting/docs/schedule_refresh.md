# Weekly Refresh Schedule

The WBR is produced by one command, `python src/run_wbr.py --week <Monday>`, so scheduling it is a single job.

| Step | Time (local) | What happens |
|---|---|---|
| Source load | Sunday by 23:59 | Daily returns, shipments and the tracker exports land in `data/raw/` |
| Tracker cut-off | Friday 17:00 | Initiative owners update status, % complete and forecast dates |
| Pipeline | Monday 06:00 | `src/schedule/run_wbr_weekly.ps1` computes last week's Monday, rebuilds the database, runs `sql/01-10`, writes the Excel WBR, the PDF and the dashboard CSVs |
| BI refresh | Monday 07:00 | Tableau extract refresh / QuickSight SPICE refresh (see `dashboard/dashboard_spec.md`) |
| Pre-read | Monday 08:00 | PDF and workbook sent to WBR attendees |
| Review | Tuesday | WBR meeting |

## Windows Task Scheduler

```
powershell -ExecutionPolicy Bypass -File src\schedule\register_wbr_task.ps1
```

This registers "Returns WBR weekly refresh" (weekly, Monday 06:00, one retry after 60 minutes, 30-minute limit). The equivalent `schtasks` one-liner is in that script. Logs go to `reports\logs\wbr_<week>.log`. A failed run returns a non-zero exit code, which shows as the task's Last Run Result and can trigger an alert.

## cron (Linux/macOS)

See `src/schedule/crontab.example`:

```
0 6 * * 1  cd /opt/returns-wbr && WEEK=$(date -d "last monday" +\%F) && .venv/bin/python src/run_wbr.py --week "$WEEK" --rebuild >> reports/logs/wbr_cron.log 2>&1 || echo "WBR failed for $WEEK" | mail -s "WBR refresh failed" returns-analytics@example.com
```

## Failure handling

- A non-Monday or out-of-range `--week` exits with an error before writing anything.
- If a query returns no rows for the week, the run stops and the previous week's artifacts stay in place.
- The data-quality log (`data/processed/data_quality_log.csv`) is rewritten every run. Review it if row counts change more than 5% week over week.

The schedule scripts are examples written for this project. They have not been registered on a production scheduler.
