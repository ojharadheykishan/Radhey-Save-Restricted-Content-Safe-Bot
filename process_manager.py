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

def start_flask():
    """Start Flask app"""
    global flask_process
    try:
        logger.info("Starting Flask app...")
        flask_process = subprocess.Popen(
            FLASK_PROCESS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )
        logger.info(f"Flask app started with PID: {flask_process.pid}")
    except Exception as e:
        logger.error(f"Failed to start Flask app: {str(e)}")

def start_bot():
    """Start Telegram bot"""
    global bot_process
    try:
        logger.info("Starting Telegram bot...")
        bot_process = subprocess.Popen(
            BOT_PROCESS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )
        logger.info(f"Telegram bot started with PID: {bot_process.pid}")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {str(e)}")

def restart_flask():
    """Restart Flask app"""
    global flask_process
    if flask_process:
        try:
            flask_process.terminate()
            time.sleep(2)
            if flask_process.poll() is None:
                flask_process.kill()
        except Exception as e:
            logger.error(f"Failed to stop Flask app: {str(e)}")
    start_flask()

def restart_bot():
    """Restart Telegram bot"""
    global bot_process
    if bot_process:
        try:
            bot_process.terminate()
            time.sleep(2)
            if bot_process.poll() is None:
                bot_process.kill()
        except Exception as e:
            logger.error(f"Failed to stop Telegram bot: {str(e)}")
    start_bot()

def check_processes():
    """Check if processes are running and restart if needed"""
    global flask_process, bot_process
    
    # Check Flask app
    if flask_process and flask_process.poll() is not None:
        logger.error("Flask app has stopped, restarting...")
        restart_flask()
    
    # Check Telegram bot
    if bot_process and bot_process.poll() is not None:
        logger.error("Telegram bot has stopped, restarting...")
        restart_bot()

def main():
    """Main process manager loop"""
    logger.info("=" * 50)
    logger.info(f"Process Manager started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    # Start initial processes
    start_flask()
    time.sleep(2)
    start_bot()
    
    # Monitor processes continuously
    while True:
        try:
            check_processes()
            
            # Log process status every 5 minutes
            if int(time.time()) % 300 == 0:
                flask_status = "Running" if flask_process and flask_process.poll() is None else "Stopped"
                bot_status = "Running" if bot_process and bot_process.poll() is None else "Stopped"
                logger.info(f"Process status - Flask: {flask_status}, Bot: {bot_status}")
            
            time.sleep(10)
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
