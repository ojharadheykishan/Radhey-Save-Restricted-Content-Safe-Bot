#safe_repo


import asyncio
import logging
from pyromod import listen
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN
from telethon.sync import TelegramClient


loop = asyncio.get_event_loop()

logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

# Initialize Telethon client (we'll start it later if needed)
sex = TelegramClient('sexrepo', API_ID, API_HASH)

app = Client(
    ":RestrictBot:",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=10,
    sleep_threshold=20,
    max_concurrent_transmissions=5
)



async def restrict_bot():
    global BOT_ID, BOT_NAME, BOT_USERNAME
    try:
        await app.start()
        getme = await app.get_me()
        BOT_ID = getme.id
        BOT_USERNAME = getme.username
        if getme.last_name:
            BOT_NAME = getme.first_name + " " + getme.last_name
        else:
            BOT_NAME = getme.first_name
        logging.info("Bot initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize bot: {e}")
        # Handle the error appropriately - maybe exit or continue
        raise


try:
    loop.run_until_complete(restrict_bot())
except Exception as e:
    logging.error(f"Bot initialization failed: {e}")
    # If initialization fails, we might want to exit
    import sys
    sys.exit(1)


