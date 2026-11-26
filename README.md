# KIRA-BOT 4.0

## Files
- `main.py` — Telegram bot code
- `requirements.txt` — Python dependency
- `Procfile` — Railway worker start command

## Railway variables
Set these in Railway → your service → Variables:

- `BOT_TOKEN` — token from BotFather
- `ADMIN_ID` — your Telegram numeric user ID
- `DB_PATH` — optional; for a Railway Volume mounted at `/data`, set `/data/kira_orders.db`

Do not put the bot token in GitHub or share it in screenshots.

## Deploy
1. Upload these files to your GitHub repository.
2. Connect the repository to a Railway service.
3. Add the variables above.
4. If using SQLite persistently, add a Railway Volume mounted at `/data` and set `DB_PATH=/data/kira_orders.db`.
5. Deploy and check the service logs for `KIRA-BOT 4.0 запущен!`.

Stop any other copy of the bot using polling (for example, in Pydroid) before starting the Railway copy. Two polling instances using the same token can conflict.
