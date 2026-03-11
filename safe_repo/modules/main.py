#safe_repo

import time
import asyncio
from pyrogram import filters, Client
from safe_repo import app
from config import API_ID, API_HASH
from safe_repo.core.get_func import get_msg
from safe_repo.core.func import *
from safe_repo.core.mongo import db, plans_db
from pyrogram.errors import FloodWait, SessionRevoked, AuthKeyDuplicated, AuthKeyUnregistered
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@app.on_message(filters.regex(r'https?://[^\s]+'))
async def single_link(_, message):
    user_id = message.chat.id
    lol = await chk_user(message, user_id)
    if lol == 1:
        return
    
    link = get_link(message.text) 
    
    userbot = None
    try:
        join = await subscribe(_, message)
        if join == 1:
            return
     
        msg = await message.reply("Processing...")
        data = await db.get_data(user_id)
        
        if data and data.get("session"):
            session = data.get("session")
            try:
                userbot = Client(":userbot:", api_id=API_ID, api_hash=API_HASH, session_string=session)
                await userbot.start()                
            except (SessionRevoked, AuthKeyDuplicated, AuthKeyUnregistered):
                return await msg.edit_text("Login expired /login again...")
            except Exception as e:
                logger.error(f"Session start error: {e}")
                return await msg.edit_text("Failed to start session. Please try again.")
        else:
            await msg.edit_text("Login in bot first ...")
            return

        try:
            if 't.me/+' in link:
                q = await userbot_join(userbot, link)
                await msg.edit_text(q)
            elif 't.me/' in link:
                await get_msg(userbot, user_id, msg.id, link, 0, message)
        except Exception as e:
            logger.error(f"Processing error: {e}")
            await msg.edit_text(f"Link: `{link}`\n\n**Error:** {str(e)}")
                     
    except FloodWait as fw:
        await msg.edit_text(f'Try again after {fw.x} seconds due to floodwait from telegram.')
    except Exception as e:
        logger.error(f"Main error: {e}")
        await app.send_message(user_id, f"Link: `{link}`\n\n**Error:** {str(e)}")
    finally:
        # Ensure userbot is properly disconnected
        if userbot:
            try:
                await userbot.stop()
            except:
                pass


users_loop = {}

@app.on_message(filters.command("settings"))
async def settings_command(_, message):
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Set Chat ID", callback_data='setchat'), InlineKeyboardButton("Set Rename Tag", callback_data='setrename')],
            [InlineKeyboardButton("Caption", callback_data='setcaption'), InlineKeyboardButton("Replace Words", callback_data='setreplacement')],
            [InlineKeyboardButton("Remove Words", callback_data='delete'), InlineKeyboardButton("Reset", callback_data='reset')],
            [InlineKeyboardButton("Login", callback_data='addsession'), InlineKeyboardButton("Logout", callback_data='logout')],
            [InlineKeyboardButton("Set Thumbnail", callback_data='setthumb'), InlineKeyboardButton("Remove Thumbnail", callback_data='remthumb')],
            [InlineKeyboardButton("Report Errors", url="https://t.me/safe_repo")]
        ]
    )
    
    await message.reply_text(
        text="Customize by your end and Configure your settings ...",
        reply_markup=buttons
    )


@app.on_callback_query()
async def callback_query_handler(_, callback_query):
    user_id = callback_query.from_user.id
    
    if callback_query.data == b'setchat':
        await callback_query.answer("Send me the ID of that chat:")
        # We'll need to implement session management for this
    elif callback_query.data == b'setrename':
        await callback_query.answer("Send me the rename tag:")
    elif callback_query.data == b'setcaption':
        await callback_query.answer("Send me the caption:")
    elif callback_query.data == b'setreplacement':
        await callback_query.answer("Send me the replacement words in the format: 'WORD(s)' 'REPLACEWORD'")
    elif callback_query.data == b'addsession':
        await callback_query.answer("This method is deprecated ... use /login")
    elif callback_query.data == b'delete':
        await callback_query.answer("Send words separated by space to delete them from caption/filename ...")
    elif callback_query.data == b'logout':
        from safe_repo.modules.login import delete_session_files
        files_deleted = await delete_session_files(user_id)
        if files_deleted:
            await callback_query.answer("Logged out and deleted session successfully.")
        else:
            await callback_query.answer("You are not logged in")
    elif callback_query.data == b'setthumb':
        await callback_query.answer('Please send the photo you want to set as the thumbnail.')
    elif callback_query.data == b'reset':
        try:
            # Clear delete words for this user
            from safe_repo.core.get_func import save_delete_words
            save_delete_words(user_id, set())
            await callback_query.answer("All words have been removed from your delete list.")
        except Exception as e:
            await callback_query.answer(f"Error clearing delete list: {e}")
    elif callback_query.data == b'remthumb':
        try:
            import os
            os.remove(f'{user_id}.jpg')
            await callback_query.answer('Thumbnail removed successfully!')
        except FileNotFoundError:
            await callback_query.answer("No thumbnail found to remove.")


@app.on_message(filters.command("batch"))
async def batch_link(_, message):
    user_id = message.chat.id    
    lol = await chk_user(message, user_id)
    if lol == 1:
        return    
    
    start = await app.ask(message.chat.id, text="Please send the start link.")
    start_id = start.text
    s = start_id.split("/")[-1]
    try:
        cs = int(s)
    except ValueError:
        await app.send_message(message.chat.id, "Invalid start link format. Please send a valid Telegram message link.")
        return
    
    last = await app.ask(message.chat.id, text="Please send the end link.")
    last_id = last.text
    l = last_id.split("/")[-1]
    try:
        cl = int(l)
    except ValueError:
        await app.send_message(message.chat.id, "Invalid end link format. Please send a valid Telegram message link.")
        return

    # Check if user is premium before enforcing batch size limit
    is_premium = await plans_db.check_premium(user_id)
    if not is_premium and cl - cs > 100:
        await app.send_message(message.chat.id, "Only 100 messages allowed in batch size... Purchase premium to fly 💸")
        return
    
    userbot = None
    try:     
        data = await db.get_data(user_id)
        
        if data and data.get("session"):
            session = data.get("session")
            try:
                userbot = Client(":userbot:", api_id=API_ID, api_hash=API_HASH, session_string=session)
                await userbot.start()                
            except (SessionRevoked, AuthKeyDuplicated, AuthKeyUnregistered):
                return await app.send_message(message.chat.id, "Your login expired ... /login again")
            except Exception as e:
                logger.error(f"Session start error: {e}")
                return await app.send_message(message.chat.id, "Failed to start session. Please try again.")
        else:
            await app.send_message(message.chat.id, "Login in bot first ...")

        try:
            users_loop[user_id] = True
            
            for i in range(int(s), int(l)):
                if user_id in users_loop and users_loop[user_id]:
                    msg = await app.send_message(message.chat.id, "Processing!")
                    try:
                        x = start_id.split('/')
                        y = x[:-1]
                        result = '/'.join(y)
                        url = f"{result}/{i}"
                        link = get_link(url)
                        await get_msg(userbot, user_id, msg.id, link, 0, message)
                        sleep_msg = await app.send_message(message.chat.id, "Sleeping for 10 seconds to avoid flood...")
                        await asyncio.sleep(8)
                        await sleep_msg.delete()
                        await asyncio.sleep(2)                                                
                    except Exception as e:
                        logger.error(f"Error processing link {url}: {e}")
                        await app.send_message(message.chat.id, f"Error processing link {url}: {str(e)}")
                        continue
                else:
                    break
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            await app.send_message(message.chat.id, f"Error: {str(e)}")
                     
    except FloodWait as fw:
        await app.send_message(message.chat.id, f'Try again after {fw.x} seconds due to floodwait from Telegram.')
    except Exception as e:
        logger.error(f"Main batch error: {e}")
        await app.send_message(message.chat.id, f"Error: {str(e)}")
    finally:
        # Ensure userbot is properly disconnected
        if userbot:
            try:
                await userbot.stop()
            except:
                pass


@app.on_message(filters.command("cancel"))
async def stop_batch(_, message):
    user_id = message.chat.id
    if user_id in users_loop:
        users_loop[user_id] = False
        await app.send_message(message.chat.id, "Batch processing stopped.")
    else:
        await app.send_message(message.chat.id, "No active batch processing to stop.")

