#safe_repo - YouTube Downloader Module
"""
YouTube Video Downloader with Full Features
Bot sends welcome message and asks for link
After link - shows quality options and other menus
"""

import os
import time
import asyncio
import logging
import re
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from safe_repo import app
from safe_repo.core.func import upload_progress_bar, humanbytes, screenshot, hhmmss, video_metadata
from config import LOG_GROUP, OWNER_ID

logger = logging.getLogger(__name__)

yt_users = {}
yt_waiting_for_link = {}

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def get_youtube_id(url):
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    elif "youtube.com/watch" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtube.com/playlist" in url:
        return "playlist"
    return None


async def get_youtube_info(url):
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"YouTube info error: {e}")
        return None


def get_available_qualities(info):
    if not info or 'formats' not in info:
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
    
    return sorted(qualities, key=lambda x: x[2], reverse=True)[:6]


async def download_youtube_video(url, format_id=None, output_path=None, is_audio=False, 
                           video_format='mp4'):
    try:
        import yt_dlp
        
        if output_path is None:
            output_path = DOWNLOADS_DIR
        
        os.makedirs(output_path, exist_ok=True)
        
        if is_audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferredcodec': 'mp3',
                    'preferredformat': 'mp3',
                }],
                'socket_timeout': 30,
                'skip_unavailable_fragments': True,
                'fragment_retries': 10,
                'noprogress': False,
            }
        else:
            if format_id:
                format_str = f'{format_id}+bestaudio/best'
            else:
                format_str = "bestvideo+bestaudio/best"
            
            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferredcodec': video_format,
                }],
                'socket_timeout': 30,
                'skip_unavailable_fragments': True,
                'fragment_retries': 10,
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


async def cut_video_ffmpeg(input_file, start_time, end_time, output_path=None):
    if output_path is None:
        output_path = DOWNLOADS_DIR
    
    try:
        os.makedirs(output_path, exist_ok=True)
        
        base_name = os.path.basename(input_file)
        name_without_ext = os.path.splitext(base_name)[0]
        ext = os.path.splitext(input_file)[1]
        
        output_file = os.path.join(output_path, f"{name_without_ext}_cut{ext}")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file,
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c", "copy",
            output_file
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_file):
            return output_file
        else:
            logger.error(f"FFmpeg cut error: {stderr.decode()}")
            return None
    
    except Exception as e:
        logger.error(f"Cut video error: {e}")
        return None


async def convert_to_mp3(input_file, output_path=None):
    if output_path is None:
        output_path = DOWNLOADS_DIR
    
    try:
        os.makedirs(output_path, exist_ok=True)
        
        base_name = os.path.basename(input_file)
        name_without_ext = os.path.splitext(base_name)[0]
        
        output_file = os.path.join(output_path, f"{name_without_ext}.mp3")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_file
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        if os.path.exists(output_file):
            return output_file
        return None
    
    except Exception as e:
        logger.error(f"Convert to MP3 error: {e}")
        return None


def parse_time(time_str):
    time_str = time_str.strip()
    
    pattern = r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$'
    match = re.match(pattern, time_str)
    
    if match:
        parts = [int(g) for g in match.groups() if g]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    
    try:
        return int(time_str)
    except:
        return None


MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📹 Download Video", callback_data="yt_menu_video")],
    [InlineKeyboardButton("🎵 Download MP3", callback_data="yt_menu_mp3")],
    [InlineKeyboardButton("✂️ Cut Video", callback_data="yt_menu_cut")],
    [InlineKeyboardButton("📋 Playlist", callback_data="yt_menu_playlist")],
    [InlineKeyboardButton("❌ Cancel", callback_data="yt_cancel")]
])


QUALITY_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📹 1080p HD", callback_data="yt_q_1080")],
    [InlineKeyboardButton("📹 720p HD", callback_data="yt_q_720")],
    [InlineKeyboardButton("📹 480p SD", callback_data="yt_q_480")],
    [InlineKeyboardButton("📹 360p", callback_data="yt_q_360")],
    [InlineKeyboardButton("🎵 MP3 Audio", callback_data="yt_get_mp3")],
    [InlineKeyboardButton("🔙 Back", callback_data="yt_back")]
])


@app.on_message(filters.command("yt") & filters.private)
async def yt_command(client, message):
    user_id = message.chat.id
    
    try:
        welcome_text = """
╭──────────────────────────────╮
│  📥 YouTube Downloader     │
│      Welcome Menu           │
├──────────────────────────────┤
│                              │
│  👋 Hello! I'm your         │
│  YouTube Downloader Bot      │
│                              │
│  I can help you:            │
│  🎬 Download Videos        │
│  🎵 Extract MP3 Audio     │
│  ✂️ Cut/Trim Videos        │
│  📋 Download Playlists    │
│                              │
│  ╭────────────────────────╮│
│  │ Send me a YouTube link ││
│  │ to get started!       ││
│  ╰────────────────────────╯│
│                              │
│  No login required!       │
│  100% Free Service         │
│                              │
╰──────────────────────────────╯
"""
        await message.reply_text(welcome_text, reply_markup=MAIN_MENU)
        
        yt_waiting_for_link[user_id] = {
            'state': 'waiting_for_link',
            'type': 'menu'
        }
    
    except Exception as e:
        logger.error(f"YT command error: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)[:100]}")


@app.on_message(filters.text & filters.private)
async def handle_link_input(client, message):
    user_id = message.chat.id
    text = message.text.strip()
    
    if user_id not in yt_waiting_for_link:
        return
    
    if "youtube.com" in text or "youtu.be" in text:
        state = yt_waiting_for_link[user_id]
        
        if "youtube.com/playlist" in text or "list=" in text:
            await handle_playlist(client, message, text)
        else:
            await handle_video_link(client, message, text)
    else:
        await message.reply_text("❌ **Invalid URL**\nPlease send a valid YouTube link.\n\nUse /yt to start again.")


async def handle_video_link(client, message, url):
    user_id = message.chat.id
    
    try:
        processing_msg = await message.reply_text("🔍 **Fetching video information...**")
        
        info = await asyncio.to_thread(get_youtube_info, url)
        
        if not info:
            await processing_msg.edit_text("❌ **Error**\nCouldn't fetch video. Please try again.")
            return
        
        qualities = get_available_qualities(info)
        
        if not qualities:
            await processing_msg.edit_text("❌ **Error**\nNo video formats available.")
            return
        
        title = info.get('title', 'Unknown')[:60]
        duration = info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}"
        views = info.get('view_count', 0)
        
        yt_users[user_id] = {
            'url': url,
            'info': info,
            'qualities': qualities,
            'state': 'quality_selection'
        }
        
        del yt_waiting_for_link[user_id]
        
        quality_buttons = []
        for q in qualities[:5]:
            quality_buttons.append([
                InlineKeyboardButton(f"📹 {q[0]}", callback_data=f"yt_quality_{q[1]}")
            ])
        quality_buttons.append([
            InlineKeyboardButton("🎵 MP3 Audio", callback_data="yt_get_mp3")
        ])
        quality_buttons.append([
            InlineKeyboardButton("❌ Cancel", callback_data="yt_cancel")
        ])
        
        quality_menu = InlineKeyboardMarkup(quality_buttons)
        
        info_text = f"""
╭──────────────────────────────╮
│  📹 Video Found             │
├──────────────────────────────┤
│                              │
│  📌 {title}...          │
│                              │
│  ⏱️  Duration: {duration_str}         │
│  👁️  Views: {views:,}            │
│                              │
│  Select Quality Below:      │
│                              │
╰──────────────────────────────╯
"""
        await processing_msg.edit_text(info_text, reply_markup=quality_menu)
    
    except Exception as e:
        logger.error(f"Handle video error: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)[:100]}")


async def handle_playlist(client, message, url):
    user_id = message.chat.id
    
    try:
        processing_msg = await message.reply_text("🔍 **Fetching playlist...**")
        
        import yt_dlp
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            await processing_msg.edit_text("❌ **Error**\nCouldn't fetch playlist.")
            return
        
        entries = info.get('entries', [])
        playlist_title = info.get('title', 'Playlist')[:40]
        
        del yt_waiting_for_link[user_id]
        
        buttons = [
            [InlineKeyboardButton(f"📥 Download All ({len(entries)} videos)", callback_data=f"yt_pl_all")],
            [InlineKeyboardButton(f"📹 Download First 5", callback_data=f"yt_pl_5")],
            [InlineKeyboardButton("❌ Cancel", callback_data="yt_cancel")]
        ]
        
        await processing_msg.edit_text(
            f"📋 **Playlist:** {playlist_title}\n\n**Videos:** {len(entries)}\n\nSelect:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    except Exception as e:
        logger.error(f"Playlist error: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)[:100]}")


@app.on_callback_query(filters.regex(r"^yt_menu_"))
async def yt_menu_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    try:
        if data == "yt_menu_video":
            await callback_query.edit_message_text(
                "📹 **Download Video**\n\nSend me the YouTube video link:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_back")]])
            )
            yt_waiting_for_link[user_id] = {'state': 'waiting_for_link', 'type': 'video'}
        
        elif data == "yt_menu_mp3":
            await callback_query.edit_message_text(
                "🎵 **Download MP3**\n\nSend me the YouTube video link:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_back")]])
            )
            yt_waiting_for_link[user_id] = {'state': 'waiting_for_link', 'type': 'mp3'}
        
        elif data == "yt_menu_cut":
            await callback_query.edit_message_text(
                "✂️ **Cut Video**\n\nSend me the YouTube video link:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_back")]])
            )
            yt_waiting_for_link[user_id] = {'state': 'waiting_for_link', 'type': 'cut'}
        
        elif data == "yt_menu_playlist":
            await callback_query.edit_message_text(
                "📋 **Download Playlist**\n\nSend me the YouTube playlist link:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_back")]])
            )
            yt_waiting_for_link[user_id] = {'state': 'waiting_for_link', 'type': 'playlist'}
        
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Menu callback error: {e}")
        await callback_query.answer("Error", show_alert=True)


@app.on_callback_query(filters.regex(r"^yt_quality_"))
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
        for q in user_data['qualities']:
            if q[1] == format_id:
                quality_label = q[0]
                break
        
        await callback_query.edit_message_text(
            f"⏳ **Downloading...**\nQuality: {quality_label}\n\nPlease wait..."
        )
        
        file_path, dl_info = await asyncio.to_thread(
            download_youtube_video, url, format_id
        )
        
        if not file_path or not os.path.exists(file_path):
            await callback_query.edit_text("❌ **Download failed**\nPlease try again.")
            return
        
        file_size = os.path.getsize(file_path)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Video')[:200]
        uploader = dl_info.get('uploader', 'Unknown')
        duration = dl_info.get('duration', 0)
        
        caption = (
            f"📹 **{title}**\n\n"
            f"👤 **Channel:** {uploader}\n"
            f"⏱️ **Duration:** {duration // 60}:{duration % 60:02d}\n"
            f"📊 **Size:** {file_size_str}\n"
            f"🎬 **Quality:** {quality_label}\n\n"
            f"✨ **Downloaded by @safe_repo**"
        )
        
        await callback_query.edit_message_text(f"📤 **Uploading...**\nSize: {file_size_str}")
        
        try:
            sent_msg = await app.send_video(
                chat_id=user_id,
                video=file_path,
                caption=caption,
                progress=upload_progress_bar,
                progress_args=(
                    f"**__Uploading: {title}__**\n",
                    callback_query.message,
                    time.time()
                )
            )
            
            try:
                await sent_msg.copy(LOG_GROUP)
            except:
                pass
            
            await callback_query.edit_message_text(
                f"✅ **Download Complete!**\n\n"
                f"**Title:** {title}\n"
                f"**Quality:** {quality_label}\n"
                f"**Size:** {file_size_str}\n\n"
                f"✨ Sent successfully!"
            )
        
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await callback_query.edit_message_text(
                f"⚠️ **Upload failed:** {str(e)[:100]}"
            )
        
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


@app.on_callback_query(filters.regex(r"^yt_get_mp3$"))
async def ytmp3_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    try:
        if user_id not in yt_users:
            await callback_query.answer("❌ Session expired. Use /yt again", show_alert=True)
            return
        
        user_data = yt_users[user_id]
        url = user_data['url']
        
        await callback_query.edit_message_text("🎵 **Downloading MP3...**")
        
        file_path, dl_info = await asyncio.to_thread(
            download_youtube_video, url, is_audio=True
        )
        
        if not file_path or not os.path.exists(file_path):
            await callback_query.edit_message_text("❌ **Download failed**\nPlease try again.")
            return
        
        mp3_file = await convert_to_mp3(file_path)
        if mp3_file and os.path.exists(mp3_file):
            if os.path.exists(file_path):
                os.remove(file_path)
            file_path = mp3_file
        
        file_size = os.path.getsize(file_path)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Audio')[:200]
        
        caption = f"🎵 **{title}**\n\n📊 **Size:** {file_size_str}\n🎬 **Format:** MP3\n\n✨ **Downloaded by @safe_repo**"
        
        await callback_query.edit_message_text(f"📤 **Uploading MP3...**\nSize: {file_size_str}")
        
        try:
            sent_msg = await app.send_audio(
                chat_id=user_id,
                audio=file_path,
                caption=caption,
                progress=upload_progress_bar,
                progress_args=(
                    f"**__Uploading: {title}__**\n",
                    callback_query.message,
                    time.time()
                )
            )
            
            try:
                await sent_msg.copy(LOG_GROUP)
            except:
                pass
            
            await callback_query.edit_message_text(
                f"✅ **Download Complete!**\n\n"
                f"**Title:** {title}\n"
                f"**Size:** {file_size_str}\n\n"
                f"✨ MP3 sent successfully!"
            )
        
        except Exception as e:
            logger.error(f"MP3 upload error: {e}")
            await callback_query.edit_message_text(f"⚠️ **Upload failed:** {str(e)[:100]}")
        
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


@app.on_callback_query(filters.regex(r"^yt_back$"))
async def yt_back_callback(client, callback_query):
    await callback_query.edit_message_text(
        "📥 **YouTube Downloader**\n\nSend me a YouTube link to get started!",
        reply_markup=MAIN_MENU
    )
    await callback_query.answer()


@app.on_callback_query(filters.regex(r"^yt_cancel$"))
async def yt_cancel_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    try:
        if user_id in yt_users:
            del yt_users[user_id]
        if user_id in yt_waiting_for_link:
            del yt_waiting_for_link[user_id]
        
        await callback_query.edit_message_text(
            "❌ **Cancelled**\n\nUse /yt to start again."
        )
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Cancel error: {e}")
        await callback_query.answer("Error", show_alert=True)