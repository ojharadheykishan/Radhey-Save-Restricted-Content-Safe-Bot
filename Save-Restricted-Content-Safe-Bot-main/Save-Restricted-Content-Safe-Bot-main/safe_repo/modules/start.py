import random
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from safe_repo import app
from safe_repo.core import script
from safe_repo.core.func import subscribe
from safe_repo.core.mongo import db as mdb
from safe_repo.core.mongo.plans_db import check_premium, add_premium
from safe_repo.core.mongo.users_db import add_user, get_user
from config import OWNER_ID, CLONE_LOG_CHANNEL
from datetime import datetime, timedelta, timezone

YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@GKWITHRK096"


def youtube_subscription_buttons(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Subscribe on YouTube", url=YOUTUBE_CHANNEL_URL)],
            [InlineKeyboardButton("I have subscribed", callback_data=f"youtube_subscribed:{user_id}")],
        ]
    )


def youtube_subscription_message(mention):
    return (
        f"Welcome {mention}!\n\n"
        "YouTube channel subscribe karna zaroori hai to activate your free premium plan.\n\n"
        "Subscribe button par click karein, phir **I have subscribed** button dabayein.\n\n"
        "Note: YouTube subscription automatic verify nahi hoti; confirmation ke baad 1-day trial activate hoga."
    )


async def activate_one_day_trial(message, user):
    user_id = user.id
    expire_date = datetime.now(timezone.utc) + timedelta(days=1)
    await add_premium(user_id, expire_date, plan_type="1_day_trial")
    if not await get_user(user_id):
        await add_user(user_id)

    await message.reply_text(
        f"🎉 **Premium activated successfully!**\n\n"
        f"📋 **Plan:** 1-day premium trial\n"
        f"⏰ **Trial Expires:** {expire_date.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        "You can now use the bot's premium features."
    )
    try:
        await app.send_message(
            chat_id=CLONE_LOG_CHANNEL,
            text=(
                "🎁 **NEW USER 1-DAY FREE TRIAL**\n\n"
                f"👤 **User:** {user.first_name or 'User'} ({user_id})\n"
                f"📱 **User ID:** `{user_id}`\n"
                f"📅 **Expires:** {expire_date.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            ),
        )
    except Exception as error:
        print(f"Failed to send trial alert: {error}")

# ------------------- Start-Buttons ------------------- #

buttons = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Help", callback_data='show_help'), InlineKeyboardButton("Settings", callback_data='show_settings')],
        [InlineKeyboardButton("Join Channel", url="https://t.me/radheyojha9")],
        [InlineKeyboardButton("Buy Premium", url="https://t.me/Radheyojha096")]
    ]
)

@app.on_message(filters.command("start"))
async def start(_, message):
    join = await subscribe(_, message)
    if join == 1:
        return
    
    user_id = message.from_user.id
    # Existing premium users and returning users can continue normally.
    premium_check = await check_premium(user_id)
    if premium_check is None:
        await message.reply_text(
            youtube_subscription_message(message.from_user.mention),
            reply_markup=youtube_subscription_buttons(user_id),
        )
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


@app.on_callback_query(filters.regex(r"^youtube_subscribed:\d+$"))
async def youtube_subscribed_callback(_, callback_query):
    expected_user_id = int(callback_query.data.split(":", 1)[1])
    if callback_query.from_user.id != expected_user_id:
        await callback_query.answer("This button belongs to another user.", show_alert=True)
        return

    if await check_premium(expected_user_id):
        await callback_query.answer("Your premium plan is already active.", show_alert=True)
        return

    await callback_query.answer("Subscription confirmed. Activating your plan...")
    await activate_one_day_trial(callback_query.message, callback_query.from_user)

@app.on_callback_query(filters.regex('show_help'))
async def show_help_callback(_, callback_query):
    help_buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Usage Instructions", callback_data='show_help2')],
            [InlineKeyboardButton("Back", callback_data='back_to_start')]
        ]
    )
    await callback_query.answer()
    await callback_query.edit_message_text(
        text=script.HELP_TXT,
        reply_markup=help_buttons
    )

@app.on_callback_query(filters.regex('show_help2'))
async def show_help2_callback(_, callback_query):
    help2_buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Back to Help", callback_data='show_help')],
            [InlineKeyboardButton("Back to Start", callback_data='back_to_start')]
        ]
    )
    await callback_query.answer()
    await callback_query.edit_message_text(
        text=script.HELP2_TXT,
        reply_markup=help2_buttons
    )

@app.on_callback_query(filters.regex('show_settings'))
async def show_settings_callback(_, callback_query):
    settings_buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Back", callback_data='back_to_start')]
        ]
    )
    await callback_query.answer()
    await callback_query.edit_message_text(
        text=script.SETTINGS_TXT,
        reply_markup=settings_buttons
    )

@app.on_message(filters.command("help"))
async def help_command(_, message):
    join = await subscribe(_, message)
    if join == 1:
        return
    
    help_buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Usage Instructions", callback_data='show_help2')],
            [InlineKeyboardButton("Back to Start", callback_data='back_to_start')]
        ]
    )
    await message.reply_text(
        text=script.HELP_TXT,
        reply_markup=help_buttons
    )

@app.on_callback_query(filters.regex('back_to_start'))
async def back_to_start_callback(_, callback_query):
    # Check if user has an active session (logged in)
    data = await mdb.get_data(callback_query.from_user.id)
    session = None
    if data:
        session = data.get("session")
    status_text = "🔓 You are logged in." if session else "🔒 You are logged out."
    
    # Get random motivational quote
    quote = random.choice(script.MOTIVATIONAL_QUOTES)
    
    await callback_query.answer()
    await callback_query.edit_message_text(
        text=script.START_TXT.format(callback_query.from_user.mention) + 
             f"\n\n{status_text}\n\n💭 **Daily Motivation:**\n\"{quote}\"",
        reply_markup=buttons
    )
