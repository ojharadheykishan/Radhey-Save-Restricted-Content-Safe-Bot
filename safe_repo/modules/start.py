from pyrogram import filters
from safe_repo import app
from safe_repo.core import script
from safe_repo.core.func import subscribe
from safe_repo.core.mongo import db as mdb
from config import OWNER_ID
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import random

# ------------------- Start-Buttons ------------------- #

buttons = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Join Channel", url="https://t.me/safe_repo")],
        [InlineKeyboardButton("Buy Premium", url="https://t.me/safe_repo_bot")]
    ]
)

@app.on_message(filters.command("start"))
async def start(_, message):
    join = await subscribe(_, message)
    if join == 1:
        return
    # Check if user has an active session (logged in)
    data = await mdb.get_data(message.from_user.id)
    session = None
    if data:
        session = data.get("session")
    status_text = "🔓 You are logged in." if session else "🔒 You are logged out."
    
    # Get random motivational quote
    quote = random.choice(script.MOTIVATIONAL_QUOTES)
    
    await message.reply_text(
        text=script.START_TXT.format(message.from_user.mention) + 
             f"\n\n{status_text}\n\n💭 **Daily Motivation:**\n\"{quote}\"",
        reply_markup=buttons
    )
