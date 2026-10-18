# Korea Stock Screener

Filters KOSPI/KOSDAQ shares for a 5-day SMA cross above the 20-day SMA **while the closing price is below the 200-day SMA**, 20-session outperformance vs KOSPI200, and increasing positive 5-session net purchases from both foreigners and pension funds.

## Run in GitHub
Actions -> Daily Korea Stock Screener -> Run workflow. Enter `2026-10-16` to backtest that date. Download the CSV from the workflow run's Artifacts section.

## Schedule
Weekdays approximately 21:30 Korea time (12:30 UTC). GitHub scheduled jobs may run late or be skipped. The default run targets the current date; exchange holidays and data delays may cause the run to fail rather than use unverified data.

## Important
This has not yet been verified against live KRX data. pykrx API endpoints can fail or change. Check `results.errors.csv` and job logs before interpreting results as a full-market screen. GitHub artifacts do not automatically get sent to ChatGPT.
