# Radhey-Save-Restricted-Content-Safe-Bot

## Run with Docker Compose

1. Copy `.env.example` to `.env` in the repository root.
2. Fill `API_ID` and `API_HASH` using the values from https://my.telegram.org/auth.
   Get `BOT_TOKEN` from @BotFather. Keep `.env` private; it is git-ignored.
3. Start the bot and web service with `docker compose up -d --build`.
4. Check startup/login errors with `docker compose logs -f bot`; stop it with
   `docker compose down`.

The existing `API_ID` remains the fallback if `API_ID` is omitted from `.env`.
The bot requires a non-empty `API_HASH` and `BOT_TOKEN` to start.