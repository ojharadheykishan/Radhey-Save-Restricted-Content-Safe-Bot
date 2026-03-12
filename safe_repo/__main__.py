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

modules_imported = False

async def safe_repo_boot():
    global modules_imported
    try:
        logger.info(f"Boot called, modules_imported: {modules_imported}")
        if not modules_imported:
            logger.info(f"Importing {len(ALL_MODULES)} modules...")
            # Track imported modules
            imported_modules = set()
            for all_module in ALL_MODULES:
                module_name = f"safe_repo.modules.{all_module}"
                if module_name not in imported_modules:
                    logger.info(f"Importing module: {all_module}")
                    importlib.import_module(module_name)
                    imported_modules.add(module_name)
            modules_imported = True
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
        logger.error(f"Error in bot boot: {e}")
        # Attempt to restart the bot after 5 seconds
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
    while True:
        try:
            loop.run_until_complete(safe_repo_boot())
            break  # Exit loop if boot completed successfully (idle was interrupted)
        except Exception as e:
            logger.error(f"Critical error: {e}")
            logger.info("Bot will not restart automatically to prevent duplicate handlers")
            break  # Exit loop to prevent duplicate handlers
    logger.info("Bot process completed")
