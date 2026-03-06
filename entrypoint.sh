#!/bin/bash

# Start the bot in the background
python3 -m safe_repo &
BOT_PID=$!

# Start the Flask server in the background
flask run -h 0.0.0.0 -p $PORT &
FLASK_PID=$!

# Function to check if services are running
check_services() {
    if ! kill -0 $BOT_PID 2>/dev/null; then
        echo "Bot process $BOT_PID has stopped. Restarting..."
        python3 -m safe_repo &
        BOT_PID=$!
    fi
    
    if ! kill -0 $FLASK_PID 2>/dev/null; then
        echo "Flask process $FLASK_PID has stopped. Restarting..."
        flask run -h 0.0.0.0 -p $PORT &
        FLASK_PID=$!
    fi
}

# Monitor services
while true; do
    check_services
    sleep 60
done
