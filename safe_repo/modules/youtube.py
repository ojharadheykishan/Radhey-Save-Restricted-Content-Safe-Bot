#safe_repo - YouTube Downloader Module
"""
YouTube Video Downloader with Quality Selection
/yt command - Download YouTube videos with multiple quality options
/ytmp3 - Download YouTube audio as MP3
/ytcut - Cut/Trim YouTube video
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
yt_downloads = {}


def get_youtube_id(url):
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    elif "youtube.com/watch" in url:
        return url.split("v=")[-1].split("&")[0]
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
    
    return sorted(qualities, key=lambda x: x[2], reverse=True)[:5]


def get_available_audio(info):
    if not info or 'formats' not in info:
        return []
    
    audio_formats = []
    seen = set()
    
    for fmt in info['formats']:
        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
            ext = fmt.get('ext', 'm4a')
            filesize = fmt.get('filesize', 0)
            
            if ext not in seen:
                quality_text = ext.upper()
                if filesize:
                    size_mb = filesize / (1024 * 1024)
                    quality_text += f" (~{size_mb:.0f}MB)"
                
                audio_formats.append((quality_text + " Audio", fmt['format_id'], ext))
                seen.add(ext)
    
    return audio_formats[:3]


async def download_youtube_video(url, format_id, output_path="downloads", is_audio=False, start_time=None, end_time=None):
    try:
        import yt_dlp
        
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
                'noprogress': True,
            }
        else:
            ydl_opts = {
                'format': f'{format_id}+bestaudio/best',
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'prefixes': ['ffmpeg', 'ffmpeg.exe'],
                    'prefixes_case_sensitive': False,
                }],
                'socket_timeout': 30,
                'skip_unavailable_fragments': True,
                'fragment_retries': 10,
                'noprogress': True,
            }
        
        if start_time and end_time:
            ydl_opts['download剪辑'] = True
            ydl_opts['download_clip_start'] = start_time
            ydl_opts['download_clip_end'] = end_time
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        if start_time and end_time and filename:
            base, ext = os.path.splitext(filename)
            new_filename = f"{base}_cut{ext}"
            if os.path.exists(filename):
                try:
                    os.rename(filename, new_filename)
                    filename = new_filename
                except:
                    pass
        
        return filename, info
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None


async def cut_video_ffmpeg(input_file, start_time, end_time, output_path="downloads"):
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


async def convert_to_mp3(input_file, output_path="downloads"):
    try:
        import yt_dlp
        
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


@app.on_message(filters.command("yt") & filters.private)
async def yt_command(client, message):
    user_id = message.chat.id
    
    try:
        if len(message.command) < 2:
            help_msg = (
                "📥 **YouTube Video Downloader**\n\n"
                "**Usage:** `/yt <YouTube_URL>`\n\n"
                "**Example:**\n"
                "`/yt https://www.youtube.com/watch?v=dQw4w9WgXcQ`\n\n"
                "**Commands:**\n"
                "📹 `/yt` - Download Video\n"
                "🎵 `/ytmp3` - Download MP3\n"
                "✂️ `/ytcut` - Cut Video\n\n"
                "**Features:**\n"
                "✅ Multiple quality options\n"
                "✅ MP3 audio download\n"
                "✅ Video cutting\n"
                "✅ No login required!\n"
            )
            await message.reply_text(help_msg)
            return
        
        url = message.command[1]
        
        if "youtube.com" not in url and "youtu.be" not in url:
            await message.reply_text("❌ **Invalid URL**\nPlease provide a valid YouTube URL.")
            return
        
        processing_msg = await message.reply_text("🔍 **Fetching video information...**\n\nPlease wait...")
        
        info = await asyncio.to_thread(get_youtube_info, url)
        
        if not info:
            await processing_msg.edit_text("❌ **Error**\nCouldn't fetch video information.")
            return
        
        qualities = get_available_qualities(info)
        
        if not qualities:
            await processing_msg.edit_text("❌ **Error**\nNo video formats available.")
            return
        
        yt_users[user_id] = {
            'url': url,
            'info': info,
            'qualities': qualities,
            'type': 'video'
        }
        
        buttons = []
        for quality_label, format_id, height in qualities:
            buttons.append([
                InlineKeyboardButton(
                    f"📹 {quality_label}",
                    callback_data=f"yt_quality_{user_id}_{format_id}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"yt_mp3_{user_id}")
        ])
        
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"yt_cancel_{user_id}")])
        
        markup = InlineKeyboardMarkup(buttons)
        
        title = info.get('title', 'Unknown Title')[:100]
        duration = info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
        
        info_text = (
            f"📹 **YouTube Video**\n\n"
            f"**Title:** `{title}`\n"
            f"**Duration:** {duration_str}\n"
            f"**Channel:** {info.get('uploader', 'Unknown')}\n\n"
            f"**Select Quality:**"
        )
        
        await processing_msg.edit_text(info_text, reply_markup=markup)
    
    except Exception as e:
        logger.error(f"YT command error: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)[:100]}")


@app.on_message(filters.command("ytmp3") & filters.private)
async def ytmp3_command(client, message):
    user_id = message.chat.id
    
    try:
        if len(message.command) < 2:
            help_msg = (
                "🎵 **YouTube MP3 Downloader**\n\n"
                "**Usage:** `/ytmp3 <YouTube_URL>`\n\n"
                "**Example:**\n"
                "`/ytmp3 https://www.youtube.com/watch?v=dQw4w9WgXcQ`\n\n"
                "**Features:**\n"
                "✅ High quality MP3\n"
                "✅ Fast download\n"
                "✅ No login required!"
            )
            await message.reply_text(help_msg)
            return
        
        url = message.command[1]
        
        if "youtube.com" not in url and "youtu.be" not in url:
            await message.reply_text("❌ **Invalid URL**\nPlease provide a valid YouTube URL.")
            return
        
        processing_msg = await message.reply_text("🔍 **Fetching video information...**")
        
        info = await asyncio.to_thread(get_youtube_info, url)
        
        if not info:
            await processing_msg.edit_text("❌ **Error**\nCouldn't fetch video information.")
            return
        
        title = info.get('title', 'Unknown')[:100]
        duration = info.get('duration', 0)
        
        await processing_msg.edit_text(
            f"🎵 **Downloading MP3...**\n\n"
            f"**Title:** {title}\n"
            f"**Duration:** {duration // 60}:{duration % 60:02d}"
        )
        
        file_path, dl_info = await asyncio.to_thread(
            download_youtube_video, url, None, is_audio=True
        )
        
        if not file_path or not os.path.exists(file_path):
            await processing_msg.edit_text("❌ **Download failed**\nPlease try again.")
            return
        
        mp3_file = await convert_to_mp3(file_path)
        if mp3_file and os.path.exists(mp3_file):
            file_path = mp3_file
        
        file_size = os.path.getsize(file_path)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Audio')[:200]
        
        caption = (
            f"🎵 **{title}**\n\n"
            f"📊 **Size:** {file_size_str}\n"
            f"🎬 **Format:** MP3\n\n"
            f"✨ **Downloaded by @safe_repo**"
        )
        
        await processing_msg.edit_text(
            f"📤 **Uploading MP3...**\n\n**Size:** {file_size_str}"
        )
        
        try:
            sent_msg = await app.send_audio(
                chat_id=user_id,
                audio=file_path,
                caption=caption,
                progress=upload_progress_bar,
                progress_args=(
                    f"**__Uploading: {title}__**\n",
                    processing_msg,
                    time.time()
                )
            )
            
            try:
                await sent_msg.copy(LOG_GROUP)
            except:
                pass
            
            await processing_msg.edit_text(
                f"✅ **Download Complete!**\n\n"
                f"**Title:** {title}\n"
                f"**Size:** {file_size_str}\n\n"
                f"✨ MP3 sent successfully!"
            )
        
        except Exception as e:
            logger.error(f"MP3 upload error: {e}")
            await processing_msg.edit_text(f"⚠️ **Upload failed:** {str(e)[:100]}")
        
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
    
    except Exception as e:
        logger.error(f"YTMP3 command error: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)[:100]}")


@app.on_message(filters.command("ytcut") & filters.private)
async def ytcut_command(client, message):
    user_id = message.chat.id
    
    try:
        args = message.command[1:]
        
        if len(args) < 3:
            help_msg = (
                "✂️ **YouTube Video Cutter**\n\n"
                "**Usage:** `/ytcut <URL> <start_time> <end_time>`\n\n"
                "**Example:**\n"
                "`/ytcut https://youtu.be/abc 0:30 1:00`\n"
                "`/ytcut https://youtu.be/abc 30 90` (in seconds)\n\n"
                "**Time Formats:**\n"
                "✅ `MM:SS` - Minutes:Seconds\n"
                "✅ `HH:MM:SS` - Hours:Minutes:Seconds\n"
                "✅ Seconds only\n\n"
                "✅ No login required!"
            )
            await message.reply_text(help_msg)
            return
        
        url = args[0]
        
        if "youtube.com" not in url and "youtu.be" not in url:
            await message.reply_text("❌ **Invalid URL**\nPlease provide a valid YouTube URL.")
            return
        
        start_time = parse_time(args[1])
        end_time = parse_time(args[2])
        
        if start_time is None or end_time is None:
            await message.reply_text("❌ **Invalid time format**\nUse MM:SS or HH:MM:SS or seconds.")
            return
        
        if start_time >= end_time:
            await message.reply_text("❌ **Invalid time**\nEnd time must be greater than start time.")
            return
        
        processing_msg = await message.reply_text("🔍 **Fetching video...**")
        
        info = await asyncio.to_thread(get_youtube_info, url)
        
        if not info:
            await processing_msg.edit_text("❌ **Error**\nCouldn't fetch video.")
            return
        
        duration = info.get('duration', 0)
        if end_time > duration:
            end_time = duration
        
        title = info.get('title', 'Unknown')[:100]
        
        await processing_msg.edit_text(
            f"⏳ **Downloading video...**\n\n"
            f"**Title:** {title}\n"
            f"**Cut:** {hhmmss(start_time)} - {hhmmss(end_time)}"
        )
        
        file_path, dl_info = await asyncio.to_thread(
            download_youtube_video, url, None, is_audio=False,
            start_time=start_time, end_time=end_time
        )
        
        if not file_path or not os.path.exists(file_path):
            await processing_msg.edit_text("❌ **Download failed**\nPlease try again.")
            return
        
        await processing_msg.edit_text("✂️ **Cutting video...**")
        
        cut_file = await cut_video_ffmpeg(file_path, start_time, end_time)
        
        if not cut_file or not os.path.exists(cut_file):
            cut_file = file_path
        
        file_size = os.path.getsize(cut_file)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Video')[:200]
        
        caption = (
            f"✂️ **{title}**\n\n"
            f"⏱️ **Duration:** {hhmmss(end_time - start_time)}\n"
            f"📊 **Size:** {file_size_str}\n"
            f"📍 **Cut:** {hhmmss(start_time)} - {hhmmss(end_time)}\n\n"
            f"✨ **Downloaded by @safe_repo**"
        )
        
        await processing_msg.edit_text(
            f"📤 **Uploading...**\n\n**Size:** {file_size_str}"
        )
        
        try:
            sent_msg = await app.send_video(
                chat_id=user_id,
                video=cut_file,
                caption=caption,
                progress=upload_progress_bar,
                progress_args=(
                    f"**__Uploading: {title}__**\n",
                    processing_msg,
                    time.time()
                )
            )
            
            try:
                await sent_msg.copy(LOG_GROUP)
            except:
                pass
            
            await processing_msg.edit_text(
                f"✅ **Cut Complete!**\n\n"
                f"**Duration:** {hhmmss(end_time - start_time)}\n"
                f"**Size:** {file_size_str}\n\n"
                f"✨ Video sent successfully!"
            )
        
        except Exception as e:
            logger.error(f"Cut upload error: {e}")
            await processing_msg.edit_text(f"⚠️ **Upload failed:** {str(e)[:100]}")
        
        finally:
            try:
                for f in [file_path, cut_file]:
                    if os.path.exists(f):
                        os.remove(f)
            except:
                pass
    
    except Exception as e:
        logger.error(f"YTCUT command error: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)[:100]}")


@app.on_callback_query(filters.regex(r"^yt_quality_"))
async def yt_quality_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    try:
        parts = data.split("_")
        user_id_cb = int(parts[2])
        format_id = "_".join(parts[3:])
        
        if user_id != user_id_cb:
            await callback_query.answer("❌ This is not your request", show_alert=True)
            return
        
        if user_id not in yt_users:
            await callback_query.answer("❌ Session expired. Please try /yt again", show_alert=True)
            return
        
        user_data = yt_users[user_id]
        url = user_data['url']
        info = user_data['info']
        
        selected_quality = None
        for quality_label, fmt_id, _ in user_data['qualities']:
            if fmt_id == format_id:
                selected_quality = quality_label
                break
        
        await callback_query.edit_message_text("⏳ **Starting download...**\nThis may take a while.")
        
        file_path, dl_info = await asyncio.to_thread(
            download_youtube_video, url, format_id
        )
        
        if not file_path or not os.path.exists(file_path):
            await callback_query.edit_message_text("❌ **Download failed**\nPlease try again.")
            return
        
        file_size = os.path.getsize(file_path)
        file_size_str = humanbytes(file_size)
        
        title = dl_info.get('title', 'Video')[:200]
        uploader = dl_info.get('uploader', 'Unknown')
        duration = dl_info.get('duration', 0)
        views = dl_info.get('view_count', 0)
        
        caption = (
            f"📹 **{title}**\n\n"
            f"👤 **Channel:** {uploader}\n"
            f"⏱️ **Duration:** {duration // 60}:{duration % 60:02d}\n"
            f"👁️ **Views:** {views:,}\n"
            f"📊 **Size:** {file_size_str}\n"
            f"🎬 **Quality:** {selected_quality}\n\n"
            f"✨ **Downloaded by @safe_repo**"
        )
        
        await callback_query.edit_message_text(
            f"📤 **Uploading video...**\n\n"
            f"**Size:** {file_size_str}\n"
            f"**Quality:** {selected_quality}"
        )
        
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
                f"**Quality:** {selected_quality}\n"
                f"**Size:** {file_size_str}\n\n"
                f"✨ Video sent successfully!"
            )
        
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await callback_query.edit_message_text(
                f"⚠️ **Video downloaded but upload failed**\n\n"
                f"❌ Error: {str(e)[:100]}"
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


@app.on_callback_query(filters.regex(r"^yt_mp3_"))
async def ytmp3_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    try:
        parts = callback_query.data.split("_")
        user_id_cb = int(parts[2])
        
        if user_id != user_id_cb:
            await callback_query.answer("❌ This is not your request", show_alert=True)
            return
        
        if user_id not in yt_users:
            await callback_query.answer("❌ Session expired. Please try /yt again", show_alert=True)
            return
        
        user_data = yt_users[user_id]
        url = user_data['url']
        info = user_data['info']
        
        title = info.get('title', 'Unknown')[:100]
        
        await callback_query.edit_message_text("🎵 **Downloading MP3...**")
        
        file_path, dl_info = await asyncio.to_thread(
            download_youtube_video, url, None, is_audio=True
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
        
        caption = (
            f"🎵 **{title}**\n\n"
            f"📊 **Size:** {file_size_str}\n"
            f"🎬 **Format:** MP3\n\n"
            f"✨ **Downloaded by @safe_repo**"
        )
        
        await callback_query.edit_message_text(f"📤 **Uploading MP3...**\n\n**Size:** {file_size_str}")
        
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


@app.on_callback_query(filters.regex(r"^yt_cancel_"))
async def yt_cancel_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    try:
        parts = callback_query.data.split("_")
        user_id_cb = int(parts[2])
        
        if user_id != user_id_cb:
            await callback_query.answer("❌ This is not your request", show_alert=True)
            return
        
        if user_id in yt_users:
            del yt_users[user_id]
        
        await callback_query.edit_message_text("❌ **Download cancelled.**\n\nUse /yt to try again.")
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Cancel callback error: {e}")
        await callback_query.answer("Error", show_alert=True)