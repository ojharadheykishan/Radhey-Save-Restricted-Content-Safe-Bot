#safe_repo


import math
import time , re
import logging
from pyrogram import enums
from config import CHANNEL_ID, OWNER_ID 
from safe_repo.core import script
from safe_repo.core.mongo.plans_db import premium_users
from safe_repo.core.progress_ui import (
    generate_progress_ui, 
    generate_animated_progress_ui,
    generate_super_animated_progress_ui,
    extract_filename
)

# Configure logging
logger = logging.getLogger(__name__)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import cv2
from pyrogram.errors import FloodWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant, UserNotParticipant
from datetime import datetime as dt
import asyncio, subprocess, re, os, time



async def chk_user(message, user_id):
    user = await premium_users()
    # Check if user is in premium list or is owner (lifetime premium)
    if user_id in user:
        return 0
    else:
        await message.reply_text("Purchase premium to do the tasks...")
        return 1



async def gen_link(app,chat_id):
   link = await app.export_chat_invite_link(chat_id)
   return link

async def subscribe(app, message):
   update_channel = CHANNEL_ID
   url = await gen_link(app, update_channel)
   if update_channel:
      try:
         user = await app.get_chat_member(update_channel, message.from_user.id)
         if user.status == "kicked":
            await message.reply_text("You are Banned. Contact -- @safe_repo")
            return 1
      except UserNotParticipant:
         await message.reply_photo(photo="https://graph.org/file/d44f024a08ded19452152.jpg",caption=script.FORCE_MSG.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Now...", url=f"{url}")]]))
         return 1
      except Exception:
         await message.reply_text("Something Went Wrong. Contact us @safe_repo...")
         return 1



async def get_seconds(time_string):
    def extract_value_and_unit(ts):
        value = ""
        unit = ""

        index = 0
        while index < len(ts) and ts[index].isdigit():
            value += ts[index]
            index += 1

        unit = ts[index:].lstrip()

        if value:
            value = int(value)

        return value, unit

    value, unit = extract_value_and_unit(time_string)

    if unit == 's':
        return value
    elif unit == 'min':
        return value * 60
    elif unit == 'hour':
        return value * 3600
    elif unit == 'day':
        return value * 86400
    elif unit == 'month':
        return value * 86400 * 30
    elif unit == 'year':
        return value * 86400 * 365
    else:
        return 0




async def progress_bar(current, total, ud_type, message, start):
    """
    Update progress bar with ANIMATED and COLORFUL Telegram UI
    Cycles through different animation styles
    """
    try:
        now = time.time()
        
        # Extract filename from ud_type
        filename = extract_filename(ud_type)
        
        # Determine operation type (Downloading or Uploading)
        if "Downloading" in ud_type:
            operation = "Downloading"
        elif "Uploading" in ud_type:
            operation = "Uploading"
        else:
            operation = "Processing"
        
        # Use animated progress UI with rotating styles
        elapsed = now - start if start else 1
        
        # Rotate between different styles based on time
        style_cycle = int(elapsed / 5) % 4
        styles = ['rainbow', 'fire', 'ice', 'tech']
        current_style = styles[style_cycle]
        
        # Generate animated progress UI
        progress_text = generate_animated_progress_ui(
            current, total, operation, filename, start, style=current_style
        )
        
        # Update message every 0.5 seconds for smooth animation
        last_update = getattr(progress_bar, 'last_update', 0.0)
        if not last_update or (now - last_update) > 0.5:
            await message.edit(text=progress_text)
            setattr(progress_bar, 'last_update', now)
    except Exception as e:
        # Log error but continue processing
        logger.error(f"Progress bar error: {e}")
        pass


async def download_progress_bar(current, total, ud_type, message, start):
    """
    Special progress bar for DOWNLOADS with super animation
    """
    try:
        now = time.time()
        
        # Extract filename from ud_type
        filename = extract_filename(ud_type)
        
        # Generate super animated progress UI
        progress_text = generate_super_animated_progress_ui(
            current, total, "Downloading", filename, start
        )
        
        # Update message every 0.5 seconds for smooth animation
        last_update = getattr(download_progress_bar, 'last_update', 0.0)
        if not last_update or (now - last_update) > 0.5:
            await message.edit(text=progress_text)
            setattr(download_progress_bar, 'last_update', now)
    except Exception as e:
        # Log error but continue processing
        logger.error(f"Download progress error: {e}")
        pass


async def upload_progress_bar(current, total, ud_type, message, start):
    """
    Special progress bar for UPLOADS with colorful animation
    """
    try:
        now = time.time()
        
        # Extract filename from ud_type
        filename = extract_filename(ud_type)
        
        # Generate animated progress UI with rainbow style
        progress_text = generate_animated_progress_ui(
            current, total, "Uploading", filename, start, style='rainbow'
        )
        
        # Update message every 0.5 seconds for smooth animation
        last_update = getattr(upload_progress_bar, 'last_update', 0.0)
        if not last_update or (now - last_update) > 0.5:
            await message.edit(text=progress_text)
            setattr(upload_progress_bar, 'last_update', now)
    except Exception as e:
        # Log error but continue processing
        logger.error(f"Upload progress error: {e}")
        pass

# Initialize last_update attributes
setattr(progress_bar, 'last_update', 0.0)
setattr(download_progress_bar, 'last_update', 0.0)
setattr(upload_progress_bar, 'last_update', 0.0)

def humanbytes(size):
    if size is None or size == 0:
        return "0 B"
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < 4:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2] 



def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)




async def userbot_join(userbot, invite_link):
    try:
        await userbot.join_chat(invite_link)
        return "Successfully joined the Channel"
    except UserAlreadyParticipant:
        return "User is already a participant."
    except (InviteHashInvalid, InviteHashExpired):
        return "Could not join. Maybe your link is expired or Invalid."
    except FloodWait:
        return "Too many requests, try again later."
    except Exception as e:
        print(e)
        return "Could not join, try joining manually."
    


def get_link(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex,string)   
    try:
        link = [x[0] for x in url][0]
        if link:
            return link
        else:
            return False
    except Exception:
        return False


def video_metadata(file):
    default_values = {'width': 1, 'height': 1, 'duration': 1}
    try:
        vcap = cv2.VideoCapture(file)
        if not vcap.isOpened():
            return default_values  # Return defaults if video cannot be opened

        width = round(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = round(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = vcap.get(cv2.CAP_PROP_FPS)
        frame_count = vcap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0:
            return default_values  # Return defaults if FPS value is zero or negative

        duration = round(frame_count / fps)
        if duration <= 0:
            return default_values  # Return defaults if duration is zero or negative

        vcap.release()
        return {'width': width, 'height': height, 'duration': duration}

    except Exception as e:
        print(f"Error in video_metadata: {e}")
        return default_values
    
def hhmmss(seconds):
    return time.strftime('%H:%M:%S',time.gmtime(seconds))

async def screenshot(video, duration, sender):
    if os.path.exists(f'{sender}.jpg'):
        return f'{sender}.jpg'
    
    # Check if ffmpeg is available
    try:
        ffmpeg_check = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await ffmpeg_check.communicate()
        ffmpeg_available = True
    except FileNotFoundError:
        ffmpeg_available = False
    
    if not ffmpeg_available:
        # If ffmpeg is not available, use a default thumbnail or skip screenshot
        # For now, we'll just return None and handle it in the caller
        logger.warning("ffmpeg not available, skipping screenshot generation")
        return None
    
    # Proceed with ffmpeg if available
    time_stamp = hhmmss(int(duration)/2)
    out = dt.now().isoformat("_", "seconds") + ".jpg"
    cmd = ["ffmpeg",
           "-ss",
           f"{time_stamp}", 
           "-i",
           f"{video}",
           "-frames:v",
           "1", 
           f"{out}",
           "-y"
          ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    x = stderr.decode().strip()
    y = stdout.decode().strip()
    if os.path.isfile(out):
        return out
    else:
        None  
