#safe_repo

import asyncio
import time
import os
import subprocess
import requests
from datetime import datetime as dt
import logging

# Configure logging
logger = logging.getLogger(__name__)
from safe_repo import app
from pyrogram import filters
from pyrogram.errors import ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid, PeerIdInvalid
from pyrogram.enums import MessageMediaType
from safe_repo.core.func import progress_bar, video_metadata, screenshot
from pyrogram.types import Message
from safe_repo.core.mongo import db
from config import LOG_GROUP
import json
import os
import cv2
from telethon import events, Button
    



def thumbnail(sender):
    return f'{sender}.jpg' if os.path.exists(f'{sender}.jpg') else None

async def get_msg(userbot, sender, edit_id, msg_link, i, message):
    edit = ""
    chat = ""
    round_message = False
    if "?single" in msg_link:
        msg_link = msg_link.split("?single")[0]
    msg_id = int(msg_link.split("/")[-1]) + int(i)

    # Ensure userbot is properly disconnected
    try:
        if 't.me/c/' in msg_link or 't.me/b/' in msg_link:
            if 't.me/b/' not in msg_link:
                chat = int('-100' + str(msg_link.split("/")[-2]))
            else:
                chat = msg_link.split("/")[-2]       
            file = ""
            try:
                chatx = message.chat.id
                msg = await userbot.get_messages(chat, msg_id)
                caption = None

                if msg.service is not None:
                    return None 
                if msg.empty is not None:
                    return None                          
                if msg.media:
                    if msg.media == MessageMediaType.WEB_PAGE:
                        target_chat_id = user_chat_ids.get(chatx, chatx)
                        edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning...")
                        safe_repo = await app.send_message(sender, msg.text.markdown)
                        if msg.pinned_message:
                            try:
                                await safe_repo.pin(both_sides=True)
                            except Exception as e:
                                await safe_repo.pin()
                        await safe_repo.copy(LOG_GROUP)                  
                        await edit.delete()
                        return
                if not msg.media:
                    if msg.text:
                        target_chat_id = user_chat_ids.get(chatx, chatx)
                        edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning...")
                        safe_repo = await app.send_message(sender, msg.text.markdown)
                        if msg.pinned_message:
                            try:
                                await safe_repo.pin(both_sides=True)
                            except Exception as e:
                                await safe_repo.pin()
                        await safe_repo.copy(LOG_GROUP)
                        await edit.delete()
                        return
                
                edit = await app.edit_message_text(sender, edit_id, "Trying to Download...")
                # Add timeout and retry mechanism for downloads
                max_retries = 3
                retry_delay = 5  # seconds
                file = None
                
                for attempt in range(max_retries):
                    try:
                        # Use larger timeout and progress updates for better reliability
                        file = await asyncio.wait_for(
                            userbot.download_media(
                                msg,
                                progress=progress_bar,
                                progress_args=("**__Downloading: __**\n", edit, time.time())
                            ),
                            timeout=3600  # 1 hour timeout for large files
                        )
                        break  # Success, exit loop
                    except asyncio.TimeoutError:
                        await app.edit_message_text(
                            sender, 
                            edit_id, 
                            f"Download timed out. Attempt {attempt + 1}/{max_retries}..."
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                    except Exception as e:
                        await app.edit_message_text(
                            sender, 
                            edit_id, 
                            f"Download failed: {str(e)}. Attempt {attempt + 1}/{max_retries}..."
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                
                if not file:
                    await app.edit_message_text(
                        sender, 
                        edit_id, 
                        "Failed to download media after multiple attempts. Please try again later."
                    )
                    return
                
                custom_rename_tag = get_user_rename_preference(chatx)
                last_dot_index = str(file).rfind('.')
                if last_dot_index != -1 and last_dot_index != 0:
                    safe_repo_ext = str(file)[last_dot_index + 1:]
                    if safe_repo_ext.isalpha() and len(safe_repo_ext) <= 4:
                        if safe_repo_ext.lower() == 'mov':
                            original_file_name = str(file)[:last_dot_index]
                            file_extension = 'mp4'
                        else:
                            original_file_name = str(file)[:last_dot_index]
                            file_extension = safe_repo_ext
                    else:
                        original_file_name = str(file)
                        file_extension = 'mp4'
                else:
                    original_file_name = str(file)
                    file_extension = 'mp4'

                delete_words = load_delete_words(chatx)
                for word in delete_words:
                    original_file_name = original_file_name.replace(word, "")
                video_file_name = original_file_name + " " + custom_rename_tag    
                new_file_name = original_file_name + " " + custom_rename_tag + "." + file_extension
                os.rename(file, new_file_name)
                file = new_file_name

                # CODES are hidden             

                await edit.edit('Trying to Uplaod ...')
                
                if msg.media == MessageMediaType.VIDEO and msg.video.mime_type in ["video/mp4", "video/x-matroska"]:

                    metadata = video_metadata(file)      
                    width= metadata['width']
                    height= metadata['height']
                    duration= metadata['duration']

                    if duration <= 300:
                        safe_repo = await app.send_video(chat_id=sender, video=file, caption=caption, height=height, width=width, duration=duration, thumb=None, progress=progress_bar, progress_args=('**UPLOADING:**\n', edit, time.time())) 
                        if msg.pinned_message:
                            try:
                                await safe_repo.pin(both_sides=True)
                            except Exception as e:
                                await safe_repo.pin()
                        await safe_repo.copy(LOG_GROUP)
                        await edit.delete()
                        return
                    
                    delete_words = load_delete_words(sender)
                    custom_caption = get_user_caption_preference(sender)
                    original_caption = msg.caption if msg.caption else ''
                    final_caption = f"{original_caption}" if custom_caption else f"{original_caption}"
                    lines = final_caption.split('\n')
                    processed_lines = []
                    for line in lines:
                        for word in delete_words:
                            line = line.replace(word, '')
                        if line.strip():
                            processed_lines.append(line.strip())
                    final_caption = '\n'.join(processed_lines)
                    replacements = load_replacement_words(sender)
                    for word, replace_word in replacements.items():
                        final_caption = final_caption.replace(word, replace_word)
                    caption = f"{final_caption}\n\n__**{custom_caption}**__" if custom_caption else f"{final_caption}"

                    target_chat_id = user_chat_ids.get(chatx, chatx)
                    
                    thumb_path = await screenshot(file, duration, chatx)              
                    try:
                        safe_repo = await app.send_video(
                            chat_id=target_chat_id,
                            video=file,
                            caption=caption,
                            supports_streaming=True,
                            height=height,
                            width=width,
                            duration=duration,
                            thumb=thumb_path,
                            progress=progress_bar,
                            progress_args=(
                            '**__Uploading...__**\n',
                            edit,
                            time.time()
                            )
                           )
                        if msg.pinned_message:
                            try:
                                await safe_repo.pin(both_sides=True)
                            except Exception as e:
                                await safe_repo.pin()
                        await safe_repo.copy(LOG_GROUP)
                    except:
                        await app.edit_message_text(sender, edit_id, "The bot is not an admin in the specified chat...")

                    os.remove(file)
                        
                elif msg.media == MessageMediaType.PHOTO:
                    await edit.edit("**`Uploading photo...`")
                    delete_words = load_delete_words(sender)
                    custom_caption = get_user_caption_preference(sender)
                    original_caption = msg.caption if msg.caption else ''
                    final_caption = f"{original_caption}" if custom_caption else f"{original_caption}"
                    lines = final_caption.split('\n')
                    processed_lines = []
                    for line in lines:
                        for word in delete_words:
                            line = line.replace(word, '')
                        if line.strip():
                            processed_lines.append(line.strip())
                    final_caption = '\n'.join(processed_lines)
                    replacements = load_replacement_words(sender)
                    for word, replace_word in replacements.items():
                        final_caption = final_caption.replace(word, replace_word)
                    caption = f"{final_caption}\n\n__**{custom_caption}**__" if custom_caption else f"{final_caption}"

                    target_chat_id = user_chat_ids.get(sender, sender)
                    safe_repo = await app.send_photo(chat_id=target_chat_id, photo=file, caption=caption)
                    if msg.pinned_message:
                        try:
                            await safe_repo.pin(both_sides=True)
                        except Exception as e:
                            await safe_repo.pin()                
                    await safe_repo.copy(LOG_GROUP)
                else:
                    thumb_path = thumbnail(chatx)
                    delete_words = load_delete_words(sender)
                    custom_caption = get_user_caption_preference(sender)
                    original_caption = msg.caption if msg.caption else ''
                    final_caption = f"{original_caption}" if custom_caption else f"{original_caption}"
                    lines = final_caption.split('\n')
                    processed_lines = []
                    for line in lines:
                        for word in delete_words:
                            line = line.replace(word, '')
                        if line.strip():
                            processed_lines.append(line.strip())
                    final_caption = '\n'.join(processed_lines)
                    replacements = load_replacement_words(chatx)
                    for word, replace_word in replacements.items():
                        final_caption = final_caption.replace(word, replace_word)
                    caption = f"{final_caption}\n\n__**{custom_caption}**__" if custom_caption else f"{final_caption}"

                    target_chat_id = user_chat_ids.get(chatx, chatx)
                    try:
                        safe_repo = await app.send_document(
                            chat_id=target_chat_id,
                            document=file,
                            caption=caption,
                            thumb=thumb_path,
                            progress=progress_bar,
                            progress_args=(
                            '**`Uploading...`**\n',
                            edit,
                            time.time()
                            )
                        )
                        if msg.pinned_message:
                            try:
                                await safe_repo.pin(both_sides=True)
                            except Exception as e:
                                await safe_repo.pin()

                        await safe_repo.copy(LOG_GROUP)
                    except:
                        await app.edit_message_text(sender, edit_id, "The bot is not an admin in the specified chat.") 
                    
                    os.remove(file)
                            
                await edit.delete()
            
            except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid):
                await app.edit_message_text(sender, edit_id, "Have you joined the channel?")
                return
            except Exception as e:
                await app.edit_message_text(sender, edit_id, f'Failed to save: `{msg_link}`\n\nError: {str(e)}')       
        else:
            edit = await app.edit_message_text(sender, edit_id, "Cloning...")
            try:
                chat = msg_link.split("/")[-2]
                await copy_message_with_chat_id(app, sender, chat, msg_id) 
                await edit.delete()
            except Exception as e:
                await app.edit_message_text(sender, edit_id, f'Failed to save: `{msg_link}`\n\nError: {str(e)}')
    finally:
        # Cleanup any temporary files
        try:
            if 'file' in locals() and file and os.path.exists(file):
                os.remove(file)
            if 'thumb_path' in locals() and thumb_path and os.path.exists(thumb_path) and thumb_path != f'{sender}.jpg':
                os.remove(thumb_path)
            # Also clean up any leftover screenshot files
            for f in os.listdir('.'):
                if f.endswith('.jpg') and f.startswith(dt.now().strftime('%Y-%m-%d')):
                    try:
                        os.remove(f)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


async def copy_message_with_chat_id(client, sender, chat_id, message_id):
    # Get the user's set chat ID, if available; otherwise, use the original sender ID
    target_chat_id = user_chat_ids.get(sender, sender)
    
    try:
        # Fetch the message using get_message
        msg = await client.get_messages(chat_id, message_id)
        
        # Modify the caption based on user's custom caption preference
        custom_caption = get_user_caption_preference(sender)
        original_caption = msg.caption if msg.caption else ''
        final_caption = f"{original_caption}" if custom_caption else f"{original_caption}"
        
        delete_words = load_delete_words(sender)
        for word in delete_words:
            final_caption = final_caption.replace(word, '  ')
        
        replacements = load_replacement_words(sender)
        for word, replace_word in replacements.items():
            final_caption = final_caption.replace(word, replace_word)
        
        caption = f"{final_caption}\n\n__**{custom_caption}**__" if custom_caption else f"{final_caption}"
        
        if msg.media:
            if msg.media == MessageMediaType.VIDEO:
                result = await client.send_video(target_chat_id, msg.video.file_id, caption=caption)
            elif msg.media == MessageMediaType.DOCUMENT:
                result = await client.send_document(target_chat_id, msg.document.file_id, caption=caption)
            elif msg.media == MessageMediaType.PHOTO:
                result = await client.send_photo(target_chat_id, msg.photo.file_id, caption=caption)
            else:
                # Use copy_message for any other media types
                result = await client.copy_message(target_chat_id, chat_id, message_id)
        else:
            # Use copy_message if there is no media
            result = await client.copy_message(target_chat_id, chat_id, message_id)

        # Attempt to copy the result to the LOG_GROUP
        try:
            await result.copy(LOG_GROUP)
        except Exception:
            pass
            
        if msg.pinned_message:
            try:
                await result.pin(both_sides=True)
            except Exception as e:
                await result.pin()

    except Exception as e:
        error_message = f"Error occurred while sending message to chat ID {target_chat_id}: {str(e)}"
        await client.send_message(sender, error_message)
        await client.send_message(sender, f"Make Bot admin in your Channel - {target_chat_id} and restart the process after /cancel")

# -------------- FFMPEG CODES ---------------

# ------------------------ Button Mode Editz FOR SETTINGS ----------------------------

# Paths for legacy storage (file-backed replacement for MongoDB)
_HERE = os.path.dirname(__file__)
_USERS_FILE = os.path.join(_HERE, "mongo", "users_storage.json")
_DATA_FILE = os.path.join(_HERE, "mongo", "data_storage.json")

def _read_json(path, default=None):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _write_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass

def load_authorized_users():
    data = _read_json(_USERS_FILE, {"users": []})
    return set(data.get("users", []))

def save_authorized_users(authorized_users):
    data = {"users": list(authorized_users)}
    _write_json(_USERS_FILE, data)

SUPER_USERS = load_authorized_users()

# Define a dictionary to store user chat IDs
user_chat_ids = {}

def load_delete_words(user_id):
    data = _read_json(_DATA_FILE, {})
    user = data.get(str(user_id), {})
    return set(user.get("clean_words") or [])

def save_delete_words(user_id, delete_words):
    data = _read_json(_DATA_FILE, {})
    u = data.get(str(user_id), {})
    u["clean_words"] = list(delete_words)
    data[str(user_id)] = u
    _write_json(_DATA_FILE, data)

def load_replacement_words(user_id):
    data = _read_json(_DATA_FILE, {})
    user = data.get(str(user_id), {})
    return user.get("replacement_words", {})

def save_replacement_words(user_id, replacements):
    data = _read_json(_DATA_FILE, {})
    u = data.get(str(user_id), {})
    u["replacement_words"] = replacements
    data[str(user_id)] = u
    _write_json(_DATA_FILE, data)

# Initialize the dictionary to store user preferences for renaming
user_rename_preferences = {}

# Initialize the dictionary to store user caption
user_caption_preferences = {}

# Function to load user session from MongoDB
def load_user_session(sender_id):
    data = _read_json(_DATA_FILE, {})
    user = data.get(str(sender_id), {})
    return user.get("session")

# Function to handle the /setrename command
async def set_rename_command(user_id, custom_rename_tag):
    # Update the user_rename_preferences dictionary
    user_rename_preferences[str(user_id)] = custom_rename_tag

# Function to get the user's custom renaming preference
def get_user_rename_preference(user_id):
    # Retrieve the user's custom renaming tag if set, or default to 'safe_repo'
    return user_rename_preferences.get(str(user_id), 'safe_repo')

# Function to set custom caption preference
async def set_caption_command(user_id, custom_caption):
    # Update the user_caption_preferences dictionary
    user_caption_preferences[str(user_id)] = custom_caption

# Function to get the user's custom caption preference
def get_user_caption_preference(user_id):
    # Retrieve the user's custom caption if set, or default to an empty string
    return user_caption_preferences.get(str(user_id), '')

# Initialize the dictionary to store user sessions

sessions = {}

SET_PIC = "settings.jpg"

