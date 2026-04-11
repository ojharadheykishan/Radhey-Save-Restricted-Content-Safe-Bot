#safe_repo - YouTube Downloader Module
"""
YouTube Video Downloader - Simple Flow
/yt -> Welcome + Ask Link -> User sends link -> Quality Options -> Download
"""

import os
import time
import asyncio
import logging
import re
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from safe_repo import app
from safe_repo.core.func import upload_progress_bar, humanbytes
from config import LOG_GROUP, OWNER_ID

logger = logging.getLogger(__name__)

FLOOD_WAIT_TIME = 0

yt_users = {}
yt_waiting_for_link = {}

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


async def get_youtube_info(url):
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True, 
            'no_warnings': True, 
            'extract_flat': False,
            'ignoreerrors': True,
            'nocheckcertificate': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"YouTube info error: {e}")
        return None


def get_available_qualities(info):
    if not info:
        return []
    
    if info.get('is_live') or info.get('live_status') == 'live':
        return [("🔴 Live Stream", "best", 0)]
    
    if 'formats' not in info:
        return []
    
    qualities = []
    seen = set()
    
    for fmt in reversed(info['formats']):
        if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
            height = fmt.get('height', 0)
            fps = fmt.get('fps', 30)
            
            if height and height not in seen:
                quality_text = f"{height}p {fps}fps"
                if fmt.get('filesize'):
                    size_mb = fmt['filesize'] / (1024 * 1024)
                    quality_text += f" (~{size_mb:.0f}MB)"
                
                qualities.append((quality_text, fmt['format_id'], height))
                seen.add(height)
    
    return sorted(qualities, key=lambda x: x[2], reverse=True)[:5]


async def download_youtube_video(url, format_id=None, is_audio=False, is_live=False):
    try:
        import yt_dlp
        
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        
        if is_audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferredcodec': 'mp3', 'preferredformat': 'mp3'}],
                'socket_timeout': 30,
                'noprogress': False,
            }
        elif is_live:
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferredcodec': 'mp4'}],
                'socket_timeout': 60,
                'noprogress': False,
                'live_flush_buffer': True,
            }
        else:
            format_str = f'{format_id}+bestaudio/best' if format_id else "bestvideo+bestaudio/best"
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferredcodec': 'mp4'}],
                'socket_timeout': 30,
                'noprogress': False,
                'continuedownload': True,
                'retries': 10,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        return filename, info
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None


async def convert_to_mp3(input_file):
    try:
        base_name = os.path.basename(input_file)
        name_without_ext = os.path.splitext(base_name)[0]
        output_file = os.path.join(DOWNLOADS_DIR, f"{name_without_ext}.mp3")
        
        cmd = ["ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_file]
        
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        
        return output_file if os.path.exists(output_file) else None
    
    except Exception as e:
        logger.error(f"Convert to MP3 error: {e}")
        return None


@app.on_message(filters.command("yt") & filters.private)
async def yt_command(client, message):
    user_id = message.chat.id
    
    try:
        if FLOOD_WAIT_TIME > 0:
            await message.reply_text(f"⏳ Please wait {FLOOD_WAIT_TIME} seconds...")
            return
            
        welcome_text = """📥 **YouTube Downloader**

👋 Welcome! Send me a YouTube link to download video or audio.

🎬 I can help you:
• Download Video in HD/SD quality
• Extract MP3 Audio

💬 Just send a YouTube link below!"""
        
        await message.reply_text(welcome_text)
        yt_waiting_for_link[user_id] = True
    
    except FloodWait as fw:
        global FLOOD_WAIT_TIME
        FLOOD_WAIT_TIME = fw.x
        logger.error(f"FloodWait: {fw.x} seconds")
        await message.reply_text(f"⏳ Please wait {fw.x} seconds...")
    except Exception as e:
        logger.error(f"YT command error: {e}")


@app.on_message(filters.text & filters.private)
async def handle_link(client, message):
    user_id = message.chat.id
    text = message.text.strip()
    
    if user_id not in yt_waiting_for_link:
        return
    
    if "youtube.com" not in text and "youtu.be" not in text:
        await message.reply_text("❌ Invalid URL! Please send a valid YouTube link.")
        return
    
    try:
        if FLOOD_WAIT_TIME > 0:
            await message.reply_text(f"⏳ Please wait {FLOOD_WAIT_TIME} seconds...")
            return
        del yt_waiting_for_link[user_id]
        
        processing_msg = await message.reply_text("🔍 Fetching video info...")
        
        info = await asyncio.to_thread(get_youtube_info, text)
        
        if not info:
            await processing_msg.edit_text("❌ Error! Couldn't fetch video.")
            return
        
        qualities = get_available_qualities(info)
        
        if not qualities:
            await processing_msg.edit_text("❌ Error! No formats available.")
            return
        
        title = info.get('title', 'Unknown')[:60]
        duration = info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}"
        views = info.get('view_count', 0)
        
        yt_users[user_id] = {
            'url': text,
            'info': info,
            'qualities': qualities,
            'msg_id': processing_msg.id
        }
        
        buttons = []
        for q in qualities[:5]:
            buttons.append([InlineKeyboardButton(f"📹 {q[0]}", callback_data=f"yt_q_{q[1]}")])
        buttons.append([InlineKeyboardButton("🎵 MP3 Audio", callback_data="yt_mp3")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="yt_cancel")])
        
        info_text = f"""📹 **Video Found**

📌 {title}
⏱️ Duration: {duration_str}
👁️ Views: {views:,}

Select Quality:"""
        
        await processing_msg.edit_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"Handle link error: {e}")
        await message.reply_text(f"❌ Error: {str(e)[:100]}")


@app.on_callback_query(filters.regex(r"^yt_q_"))
async def yt_quality_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    try:
        format_id = data.split("_")[1]
        
        if user_id not in yt_users:
            await callback_query.answer("❌ Session expired. Use /yt again", show_alert=True)
            return
        
        user_data = yt_users[user_id]
        url = user_data['url']
        info = user_data['info']
        
        quality_label = None
        is_live = False
        for q in user_data['qualities']:
            if q[1] == format_id:
                quality_label = q[0]
                if q[0] == "🔴 Live Stream":
                    is_live = True
                break
        
        await callback_query.edit_message_text(f"⏳ Downloading... {quality_label}")
        
        file_path, dl_info = await asyncio.to_thread(download_youtube_video, url, format_id, is_live=is_live)
        
        if not file_path or not os.path.exists(file_path):
            await callback_query.edit_message_text("❌ Download failed!")
            return
        
        file_size = os.path.getsize(file_path)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Video')[:200]
        uploader = dl_info.get('uploader', 'Unknown')
        duration = dl_info.get('duration', 0)
        
        caption = f"📹 {title}\n\n👤 {uploader}\n⏱️ {duration//60}:{duration%60:02d}\n📊 {file_size_str}\n🎬 {quality_label}\n\n✨ @safe_repo"
        
        await callback_query.edit_message_text(f"📤 Uploading... {file_size_str}")
        
        try:
            sent_msg = await app.send_video(chat_id=user_id, video=file_path, caption=caption, progress=upload_progress_bar, progress_args=(title, callback_query.message, time.time()))
            try:
                await sent_msg.copy(LOG_GROUP)
            except:
                pass
            await callback_query.edit_message_text(f"✅ Done!\n\n{title}\nSize: {file_size_str}")
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await callback_query.edit_message_text(f"⚠️ Upload failed: {str(e)[:100]}")
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        if user_id in yt_users:
            del yt_users[user_id]
        
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Quality callback error: {e}")
        await callback_query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@app.on_callback_query(filters.regex(r"^yt_mp3$"))
async def ytmp3_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    try:
        if user_id not in yt_users:
            await callback_query.answer("❌ Session expired. Use /yt again", show_alert=True)
            return
        
        user_data = yt_users[user_id]
        url = user_data['url']
        
        await callback_query.edit_message_text("🎵 Downloading MP3...")
        
        file_path, dl_info = await asyncio.to_thread(download_youtube_video, url, is_audio=True)
        
        if not file_path or not os.path.exists(file_path):
            await callback_query.edit_message_text("❌ Download failed!")
            return
        
        mp3_file = await convert_to_mp3(file_path)
        if mp3_file and os.path.exists(mp3_file):
            if os.path.exists(file_path):
                os.remove(file_path)
            file_path = mp3_file
        
        file_size = os.path.getsize(file_path)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Audio')[:200]
        
        caption = f"🎵 {title}\n\n📊 {file_size_str}\nFormat: MP3\n\n✨ @safe_repo"
        
        await callback_query.edit_message_text(f"📤 Uploading MP3... {file_size_str}")
        
        try:
            sent_msg = await app.send_audio(chat_id=user_id, audio=file_path, caption=caption, progress=upload_progress_bar, progress_args=(title, callback_query.message, time.time()))
            try:
                await sent_msg.copy(LOG_GROUP)
            except:
                pass
            await callback_query.edit_message_text(f"✅ Done!\n\n{title}\nSize: {file_size_str}")
        except Exception as e:
            logger.error(f"MP3 upload error: {e}")
            await callback_query.edit_message_text(f"⚠️ Upload failed: {str(e)[:100]}")
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        if user_id in yt_users:
            del yt_users[user_id]
        
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"MP3 callback error: {e}")
        await callback_query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@app.on_callback_query(filters.regex(r"^yt_cancel$"))
async def yt_cancel_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    try:
        if user_id in yt_users:
            del yt_users[user_id]
        if user_id in yt_waiting_for_link:
            del yt_waiting_for_link[user_id]
        
        await callback_query.edit_message_text("❌ Cancelled! Use /yt to start again.")
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Cancel error: {e}")
        await callback_query.answer("Error", show_alert=True)