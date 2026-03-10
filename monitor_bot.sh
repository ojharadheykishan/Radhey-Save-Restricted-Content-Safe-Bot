#!/bin/bash

# Monitor bot and restart if necessary
BOT_PID=$(ps aux | grep python3 | grep -v grep | awk '{print $2}')

if [ -z "$BOT_PID" ]; then
    echo "Bot is not running. Restarting..."
    nohup python3 -m safe_repo > bot.log 2>&1 &
    echo "Bot restarted with PID: $!"
else
    echo "Bot is running with PID: $BOT_PID"
fi

# Check if bot responds to API calls
RESPONSE=$(curl -s "https://api.telegram.org/bot8564747078:AAF39Ekn22SZxQB7ShELURFel981IFhrmoM/getMe")

if echo "$RESPONSE" | grep -q "ok\":true"; then
    echo "Bot is responding to API calls: $RESPONSE"
else
    echo "Bot is not responding to API calls. Restarting..."
    pkill -f python3
    sleep 2
    nohup python3 -m safe_repo > bot.log 2>&1 &
    echo "Bot restarted with PID: $!"
fi