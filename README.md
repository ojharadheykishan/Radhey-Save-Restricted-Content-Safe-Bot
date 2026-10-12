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

## Deploy on Railway

Connect this repository's `main` branch as a Docker service. In Railway's
service Variables, set `API_ID`, `API_HASH`, and `BOT_TOKEN`; these are not
read from a local `.env` file during deployment. Generate a public domain under
Settings > Networking, or set `PUBLIC_BASE_URL` to that domain with `https://`.
To keep the media catalog and cached video files across redeploys, attach a
Railway Volume mounted at `/data` and set `APP_DATA_DIR=/data`.