#safe_repo

import asyncio
import importlib
import pyrogram.utils
from pyrogram import idle
from safe_repo.modules import ALL_MODULES
from aiojobs import create_scheduler
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999
from safe_repo.core.mongo.plans_db import check_and_remove_expired_users
import logging
import sys

# Configure logging
logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()

async def schedule_expiry_check():
    scheduler = await create_scheduler()
    while True:
        try:
            await scheduler.spawn(check_and_remove_expired_users())
            logger.info("Expiry check completed successfully")
        except Exception as e:
            logger.error(f"Error in expiry check: {str(e)}")
        await asyncio.sleep(3600)  # Check every hour

async def safe_repo_boot():
    try:
        for all_module in ALL_MODULES:
            importlib.import_module("safe_repo.modules." + all_module)
        logger.info("»»»» ʙᴏᴛ ᴅᴇᴘʟᴏʏ sᴜᴄᴄᴇssғᴜʟʟʏ ✨ 🎉")

        # Start the background task for checking expired users
        asyncio.create_task(schedule_expiry_check())

        # Keep bot running indefinitely
        await idle()
        logger.warning("Bot idle loop exited")
        
    except Exception as e:
        logger.error(f"Critical error in bot boot: {str(e)}", exc_info=True)
        # Restart the bot after 5 seconds
        logger.info("Restarting bot in 5 seconds...")
        await asyncio.sleep(5)
        python = sys.executable
        os.execl(python, python, *sys.argv)

if __name__ == "__main__":
    import os
    try:
        loop.run_until_complete(safe_repo_boot())
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}", exc_info=True)
        logger.info("Restarting bot in 5 seconds...")
        import time
        time.sleep(5)
        python = sys.executable
        os.execl(python, python, *sys.argv)
