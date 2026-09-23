import threading

from app import app, register_api_routes, start_bot_process


register_api_routes(app)
threading.Thread(target=start_bot_process, daemon=True).start()