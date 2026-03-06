import os
import time
import threading
import requests
import logging
from flask import Flask

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("flask.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Auto-ping settings
AUTO_PING_ENABLED = True
AUTO_PING_INTERVAL = 300  # 5 minutes in seconds
APP_URL = None


def auto_ping():
    """Background task to keep the app awake by pinging itself periodically"""
    while AUTO_PING_ENABLED and APP_URL:
        try:
            response = requests.get(f"{APP_URL}/health", timeout=30)
            logger.info(f"Auto-ping successful: {response.status_code}")
        except Exception as e:
            logger.error(f"Auto-ping failed: {str(e)}")
        time.sleep(AUTO_PING_INTERVAL)


@app.route('/')
def home():
    return """
    <center>
        <!-- Safe_repo -->
    </center>
    <style>
        body {
            background: antiquewhite;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100vh;
            margin: 0;
        }
        footer {
            text-align: center;
            padding: 10px;
            background: antiquewhite;
            font-size: 1.2em;
        }
    </style>
    <footer>
        Made with 💕 by t.me/Safe_repo
    </footer>
    """


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    # Determine the app URL for auto-ping
    # For Render, the URL will be provided in the RENDER_EXTERNAL_URL environment variable
    if 'RENDER_EXTERNAL_URL' in os.environ:
        APP_URL = os.environ['RENDER_EXTERNAL_URL']
        logger.info(f"App URL: {APP_URL}")
        
        # Start auto-ping background task
        if AUTO_PING_ENABLED:
            ping_thread = threading.Thread(target=auto_ping, daemon=True)
            ping_thread.start()
            logger.info(f"Auto-ping service started (interval: {AUTO_PING_INTERVAL} seconds)")
    else:
        # For local or other deployments, try to get app URL from environment variables
        possible_urls = [
            os.environ.get('APP_URL'),
            os.environ.get('HEROKU_APP_NAME'),
            os.environ.get('VERCEL_URL')
        ]
        for url in possible_urls:
            if url:
                APP_URL = url if url.startswith('http') else f'https://{url}'
                logger.info(f"App URL detected from environment: {APP_URL}")
                if AUTO_PING_ENABLED:
                    ping_thread = threading.Thread(target=auto_ping, daemon=True)
                    ping_thread.start()
                    logger.info(f"Auto-ping service started (interval: {AUTO_PING_INTERVAL} seconds)")
                break
    
    logger.info(f"Flask app starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
