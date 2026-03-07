#!/usr/bin/env python3
"""
Process Manager for Safe Repo Bot
Ensures both Flask app and Telegram bot are running continuously
and restart them if they fail.
"""

import subprocess
import time
import logging
import os
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("process_manager.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Process configuration
FLASK_PROCESS = ["python3", "app.py"]
BOT_PROCESS = ["python3", "-m", "safe_repo"]

# Process handles
flask_process = None
bot_process = None

# Restart counters
flask_restart_count = 0
bot_restart_count = 0

# Maximum allowed restarts per hour
MAX_RESTARTS_PER_HOUR = 10

def start_flask():
    """Start Flask app"""
    global flask_process, flask_restart_count
    try:
        logger.info("Starting Flask app...")
        flask_process = subprocess.Popen(
            FLASK_PROCESS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        logger.info(f"Flask app started with PID: {flask_process.pid}")
        flask_restart_count += 1
        return True
    except Exception as e:
        logger.error(f"Failed to start Flask app: {str(e)}")
        return False

def start_bot():
    """Start Telegram bot"""
    global bot_process, bot_restart_count
    try:
        logger.info("Starting Telegram bot...")
        bot_process = subprocess.Popen(
            BOT_PROCESS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        logger.info(f"Telegram bot started with PID: {bot_process.pid}")
        bot_restart_count += 1
        return True
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {str(e)}")
        return False

def restart_flask():
    """Restart Flask app"""
    global flask_process
    if flask_process:
        try:
            flask_process.terminate()
            time.sleep(3)
            if flask_process.poll() is None:
                flask_process.kill()
                time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to stop Flask app: {str(e)}")
    return start_flask()

def restart_bot():
    """Restart Telegram bot"""
    global bot_process
    if bot_process:
        try:
            bot_process.terminate()
            time.sleep(3)
            if bot_process.poll() is None:
                bot_process.kill()
                time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to stop Telegram bot: {str(e)}")
    return start_bot()

def check_processes():
    """Check if processes are running and restart if needed"""
    global flask_process, bot_process, flask_restart_count, bot_restart_count
    
    # Check Flask app
    if flask_process and flask_process.poll() is not None:
        logger.error("Flask app has stopped, restarting...")
        if restart_flask():
            logger.info("Flask app restarted successfully")
        else:
            logger.critical("Failed to restart Flask app")
    
    # Check Telegram bot
    if bot_process and bot_process.poll() is not None:
        logger.error("Telegram bot has stopped, restarting...")
        if restart_bot():
            logger.info("Telegram bot restarted successfully")
        else:
            logger.critical("Failed to restart Telegram bot")
    
    # Check if we need to log process status
    if int(time.time()) % 180 == 0:  # Log every 3 minutes
        flask_status = "Running" if flask_process and flask_process.poll() is None else "Stopped"
        bot_status = "Running" if bot_process and bot_process.poll() is None else "Stopped"
        logger.info(f"Process status - Flask: {flask_status}, Bot: {bot_status} | Restarts: Flask={flask_restart_count}, Bot={bot_restart_count}")
    
    # Check for too many restarts
    if flask_restart_count > MAX_RESTARTS_PER_HOUR or bot_restart_count > MAX_RESTARTS_PER_HOUR:
        logger.critical(f"Too many restarts detected (Flask: {flask_restart_count}, Bot: {bot_restart_count})")
        logger.critical("Process manager will exit to prevent infinite restart loop")
        sys.exit(1)

def main():
    """Main process manager loop"""
    logger.info("=" * 50)
    logger.info(f"Process Manager started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Maximum restarts per hour: {MAX_RESTARTS_PER_HOUR}")
    logger.info("=" * 50)
    
    # Start initial processes
    if not start_flask():
        logger.critical("Failed to start Flask app initially")
        sys.exit(1)
    time.sleep(3)  # Give Flask more time to start
    
    if not start_bot():
        logger.critical("Failed to start Telegram bot initially")
        sys.exit(1)
    
    # Monitor processes continuously
    while True:
        try:
            check_processes()
            time.sleep(8)  # Check processes more frequently
        except Exception as e:
            logger.error(f"Error in process manager: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Process Manager stopped by user")
        if flask_process:
            flask_process.terminate()
        if bot_process:
            bot_process.terminate()
    except Exception as e:
        logger.error(f"Process Manager failed: {str(e)}")
        import sys
        sys.exit(1)
