#!/bin/bash

# Run monitor_bot.sh every 5 minutes
while true; do
    ./monitor_bot.sh
    sleep 300  # 5 minutes
done