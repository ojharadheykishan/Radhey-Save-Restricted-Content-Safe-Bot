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
AUTO_PING_INTERVAL = 120  # 2 minutes in seconds (more frequent to prevent sleep)
APP_URL = None


def auto_ping():
    """Background task to keep the app awake by pinging itself periodically"""
    while AUTO_PING_ENABLED:
        if APP_URL:
            try:
                response = requests.get(f"{APP_URL}/health", timeout=30)
                logger.info(f"Auto-ping successful: {response.status_code}")
            except Exception as e:
                logger.error(f"Auto-ping failed: {str(e)}")
                # Try to detect app URL again if ping fails
                detect_app_url()
        else:
            # If no app URL detected, try to detect it
            detect_app_url()
        
        time.sleep(AUTO_PING_INTERVAL)


def detect_app_url():
    """Detect app URL from environment variables"""
    global APP_URL
    
    # Check Render URL
    if 'RENDER_EXTERNAL_URL' in os.environ:
        APP_URL = os.environ['RENDER_EXTERNAL_URL']
        logger.info(f"App URL detected from Render: {APP_URL}")
        return True
    
    # Check Heroku URL
    if 'HEROKU_APP_NAME' in os.environ:
        APP_URL = f"https://{os.environ['HEROKU_APP_NAME']}.herokuapp.com"
        logger.info(f"App URL detected from Heroku: {APP_URL}")
        return True
    
    # Check Vercel URL
    if 'VERCEL_URL' in os.environ:
        APP_URL = os.environ['VERCEL_URL'] if os.environ['VERCEL_URL'].startswith('http') else f"https://{os.environ['VERCEL_URL']}"
        logger.info(f"App URL detected from Vercel: {APP_URL}")
        return True
    
    # Check custom APP_URL
    if 'APP_URL' in os.environ:
        APP_URL = os.environ['APP_URL'] if os.environ['APP_URL'].startswith('http') else f"https://{os.environ['APP_URL']}"
        logger.info(f"App URL detected from APP_URL variable: {APP_URL}")
        return True
    
    logger.warning("No app URL could be detected from environment variables")
    return False


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
    
    # Detect app URL for auto-ping
    detect_app_url()
    
    # Start auto-ping background task regardless of platform
    if AUTO_PING_ENABLED:
        ping_thread = threading.Thread(target=auto_ping, daemon=True)
        ping_thread.start()
        logger.info(f"Auto-ping service started (interval: {AUTO_PING_INTERVAL} seconds)")
    
    logger.info(f"Flask app starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
