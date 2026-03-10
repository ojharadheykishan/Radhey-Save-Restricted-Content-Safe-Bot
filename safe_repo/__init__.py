#safe_repo


import asyncio
import logging
from pyromod import listen
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN


loop = asyncio.get_event_loop()

logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

# Optimized Pyrogram client configuration for better stability
# Increased sleep_threshold for large media uploads
app = Client(
    ":RestrictBot:",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=20,
    sleep_threshold=300,  # 5 minutes for large file transfers
    max_concurrent_transmissions=1  # Limit to 1 concurrent transfer to prevent timeouts
)


async def restrict_bot():
    global BOT_ID, BOT_NAME, BOT_USERNAME
    await app.start()
    getme = await app.get_me()
    BOT_ID = getme.id
    BOT_USERNAME = getme.username
    if getme.last_name:
        BOT_NAME = getme.first_name + " " + getme.last_name
    else:
        BOT_NAME = getme.first_name
    logging.info(f"Bot initialized: {BOT_NAME} (@{BOT_USERNAME})")


# Run initialization
loop.run_until_complete(restrict_bot())


