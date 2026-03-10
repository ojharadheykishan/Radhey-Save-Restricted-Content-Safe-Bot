#safe_repo

import asyncio
import importlib
import logging
import pyrogram.utils
from pyrogram import idle
from safe_repo.modules import ALL_MODULES
from aiojobs import create_scheduler
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999
from safe_repo.core.mongo.plans_db import check_and_remove_expired_users

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()

async def schedule_expiry_check():
    scheduler = await create_scheduler()
    while True:
        try:
            await scheduler.spawn(check_and_remove_expired_users())
        except Exception as e:
            logger.error(f"Error in expiry check: {e}")
        await asyncio.sleep(3600)  # Check every hour

async def safe_repo_boot():
    try:
        for all_module in ALL_MODULES:
            importlib.import_module("safe_repo.modules." + all_module)
        logger.info("»»»» ʙᴏᴛ ᴅᴇᴘʟᴏʏ sᴜᴄᴄᴇssғᴜʟʟʏ ✨ 🎉")

        # Start the background task for checking expired users
        asyncio.create_task(schedule_expiry_check())

        await idle()
        logger.info("»» ɢᴏᴏᴅ ʙʏᴇ ! sᴛᴏᴘᴘɪɴɢ ʙᴏᴛ.")
    except Exception as e:
        logger.error(f"Error in bot boot: {e}")
        # Attempt to restart the bot after 5 seconds
        logger.info("Attempting to restart bot in 5 seconds...")
        await asyncio.sleep(5)
        await safe_repo_boot()

if __name__ == "__main__":
    try:
        loop.run_until_complete(safe_repo_boot())
    except Exception as e:
        logger.error(f"Critical error: {e}")
        # Attempt to restart the event loop
        loop.run_until_complete(safe_repo_boot())
    finally:
        logger.info("Bot process completed")
