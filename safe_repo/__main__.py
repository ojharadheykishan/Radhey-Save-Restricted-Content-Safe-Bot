#safe_repo

import asyncio
import importlib
import logging
from aiojobs import create_scheduler
from pyrogram import idle
from safe_repo.modules import ALL_MODULES
from safe_repo.core.mongo.plans_db import check_and_remove_expired_users

# Fix Pyrogram channel ID limitation
import pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()

async def keep_alive_task():
    """Background task to keep the bot alive and prevent sleep mode"""
    logger.info("Keep-alive task started")
    while True:
        try:
            # Simple ping to keep the session active
            logger.debug("Bot is alive and responding")
            await asyncio.sleep(60)  # Ping every 60 seconds
        except Exception as e:
            logger.error(f"Keep-alive task error: {e}")
            await asyncio.sleep(30)

async def schedule_expiry_check():
    scheduler = await create_scheduler()
    while True:
        try:
            await scheduler.spawn(check_and_remove_expired_users())
        except Exception as e:
            logger.error(f"Error in expiry check: {e}")
        await asyncio.sleep(3600)  # Check every hour

import sys

async def safe_repo_boot():
    try:
        logger.info(f"Importing {len(ALL_MODULES)} modules...")
        # Track imported modules and prevent re-importing
        for all_module in ALL_MODULES:
            module_name = f"safe_repo.modules.{all_module}"
            if module_name not in sys.modules:
                logger.info(f"Importing module: {all_module}")
                importlib.import_module(module_name)
            else:
                logger.debug(f"Module already imported: {all_module}")
        logger.info("»»»» ʙᴏᴛ ᴅᴇᴘʟᴏʏ sᴜᴄᴄᴇssғᴜʟʟʏ ✨ 🎉")

        # Start background tasks
        asyncio.create_task(schedule_expiry_check())
        asyncio.create_task(keep_alive_task())

        # Start the Pyrogram client
        from safe_repo import app
        await app.start()
        logger.info("Bot client started successfully")
        
        await idle()
        logger.info("»» ɢᴏᴏᴅ ʙʏᴇ ! sᴛᴏᴘᴘɪɴɢ ʙᴏᴛ.")
        await app.stop()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in bot boot: {error_msg}")
        
        # Check if it's a FLOOD_WAIT error and extract wait time
        if "FLOOD_WAIT" in error_msg and "wait of" in error_msg:
            try:
                # Extract the number of seconds from the error message
                # Format: "[420 FLOOD_WAIT_X] - A wait of 1471 seconds is required"
                import re
                match = re.search(r"wait of (\d+) seconds", error_msg)
                if match:
                    wait_time = int(match.group(1))
                    logger.info(f"Telegram flood wait detected. Waiting {wait_time} seconds before restart...")
                    await asyncio.sleep(wait_time)
                else:
                    # Default wait time if we can't parse it
                    logger.info("Telegram flood wait detected. Waiting 60 seconds before restart...")
                    await asyncio.sleep(60)
            except Exception as parse_error:
                logger.error(f"Error parsing flood wait time: {parse_error}")
                logger.info("Waiting 60 seconds before restart...")
                await asyncio.sleep(60)
        else:
            # For non-flood errors, wait a shorter time
            logger.info("Attempting to restart bot in 5 seconds...")
            await asyncio.sleep(5)
        
        # Instead of recursive call, just stop and let the outer loop restart
        try:
            from safe_repo import app
            await app.stop()
        except:
            pass
        raise

if __name__ == "__main__":
    try:
        loop.run_until_complete(safe_repo_boot())
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.info("Bot will not restart automatically to prevent duplicate handlers")
    logger.info("Bot process completed")
