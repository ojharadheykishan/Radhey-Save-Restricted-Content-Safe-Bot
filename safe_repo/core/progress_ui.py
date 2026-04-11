#safe_repo - Enhanced Progress UI Module

import time
from datetime import datetime

def humanbytes(size):
    """Convert bytes to human readable format"""
    if size is None or size == 0:
        return "0 B"
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < 4:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def convert_seconds(seconds):
    """Convert seconds to HH:MM:SS format"""
    seconds = int(seconds) % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%02d:%02d:%02d" % (hour, minutes, seconds)


def get_file_type_emoji(filename):
    """Detect file type and return appropriate emoji and type name"""
    if not filename or filename == "Unknown":
        return "📄", "Unknown"
    
    filename_lower = filename.lower()
    
    # Video files
    if any(ext in filename_lower for ext in ['.mp4', '.mkv', '.mov', '.avi', '.flv', '.wmv', '.webm']):
        return "🎬", "Video/MKV"
    # Audio files
    elif any(ext in filename_lower for ext in ['.mp3', '.wav', '.aac', '.flac', '.m4a', '.wma']):
        return "🎵", "Audio"
    # Document files
    elif any(ext in filename_lower for ext in ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx']):
        return "📑", "Document"
    # Image files
    elif any(ext in filename_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
        return "🖼", "Image"
    # Archive files
    elif any(ext in filename_lower for ext in ['.zip', '.rar', '.7z', '.tar', '.gz']):
        return "📦", "Archive"
    # Code files
    elif any(ext in filename_lower for ext in ['.py', '.js', '.html', '.css', '.java', '.cpp']):
        return "💻", "Code"
    else:
        return "📄", "File"


def create_fire_progress_bar(current, total, bar_length=10):
    """Create a fire-themed progress bar with emojis"""
    if total == 0:
        return "🔸" * bar_length
    
    filled = int(bar_length * current / total)
    empty = bar_length - filled
    
    # 🟧 for filled (orange fire), 🔸 for empty (red diamond)
    return "🟧" * filled + "🔸" * empty


def format_operation_type(operation):
    """Determine operation emoji and text"""
    if "Downloading" in operation or "Download" in operation:
        return "📥", "Download"
    elif "Uploading" in operation or "Upload" in operation:
        return "📤", "Upload"
    else:
        return "🔄", "Processing"


def extract_filename(operation_text):
    """Extract filename from operation text"""
    filename = "Unknown"
    if ":" in operation_text:
        try:
            filename = operation_text.split(":", 1)[1].replace("**", "").replace("__", "").strip()
        except Exception:
            filename = operation_text.strip("*_: \n ")
    else:
        filename = operation_text.strip("*_: \n ")
    
    return filename if filename else "Unknown"


def generate_progress_ui(current, total, operation, filename, start_time):
    """
    Generate a beautiful progress message inspired by the Telegram UI mockup
    
    Args:
        current: Current bytes downloaded/uploaded
        total: Total bytes to download/upload
        operation: "Downloading" or "Uploading" 
        filename: Name of the file being transferred
        start_time: Start time of the transfer
    
    Returns:
        Formatted progress message string
    """
    
    now = time.time()
    elapsed = now - start_time if start_time else 1
    percentage = 0 if total == 0 else (current * 100) / total
    speed = current / elapsed if elapsed > 0 else 0
    
    # Calculate ETA
    if speed > 0:
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
    else:
        eta_seconds = 0
    
    # Get operation type
    op_emoji, op_text = format_operation_type(operation)
    
    # Get file type
    file_emoji, file_type = get_file_type_emoji(filename)
    
    # Create progress bar with fire emojis
    progress_bar = create_fire_progress_bar(current, total, 10)
    
    # Format sizes and speeds
    current_text = humanbytes(current)
    total_text = humanbytes(total)
    speed_text = humanbytes(speed)
    
    # Format times
    elapsed_str = convert_seconds(elapsed)
    eta_str = convert_seconds(eta_seconds) if eta_seconds > 0 else "00:00:00"
    
    # Build the message
    message = (
        f"🚀 {op_text} In Progress...\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"📂 Name: `{filename}`\n"
        f"🆔 Type: {file_type}\n"
        f"\n"
        f"{progress_bar} {percentage:.1f}%\n"
        f"\n"
        f"⚡ Speed: {speed_text}/s\n"
        f"📦 Done: {current_text} of {total_text}\n"
        f"\n"
        f"⏳ Elapsed: {elapsed_str}\n"
        f"⏱️ ETA: {eta_str}\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"✨ R A D H E Y ⚡"
    )
    
    return message


def generate_compact_progress_ui(current, total, operation, filename, start_time):
    """
    Generate a compact version of the progress UI (for smaller screens/channels)
    """
    
    now = time.time()
    elapsed = now - start_time if start_time else 1
    percentage = 0 if total == 0 else (current * 100) / total
    speed = current / elapsed if elapsed > 0 else 0
    
    # Get operation type
    op_emoji, op_text = format_operation_type(operation)
    
    # Create progress bar
    progress_bar = create_fire_progress_bar(current, total, 8)
    
    # Format sizes
    current_text = humanbytes(current)
    total_text = humanbytes(total)
    speed_text = humanbytes(speed)
    
    # Format time
    elapsed_str = convert_seconds(elapsed)
    
    # Compact message
    message = (
        f"{op_emoji} **{op_text}** • `{filename}`\n"
        f"{progress_bar} {percentage:.1f}%\n"
        f"⚡ {speed_text}/s • 📦 {current_text}/{total_text}"
    )
    
    return message


# ============ ANIMATED & COLORFUL PROGRESS BARS ============

def create_colorful_progress_bar(current, total, bar_length=10, style='rainbow', current_time=None):
    """
    Create an animated and colorful progress bar with multiple theme options
    
    Styles:
    - 'rainbow': 🟦🟩🟨🟧🟥 gradient
    - 'fire': 🔴🟠🟡 fire gradient  
    - 'ice': 🔵💙🟦 ice gradient
    - 'neon': 🟪🟩 neon effect
    - 'tech': ▓░ tech style
    - 'animated': Animated bars
    """
    if total == 0:
        if style == 'tech':
            return "░" * bar_length
        else:
            return "⚪" * bar_length
    
    filled = int(bar_length * current / total)
    empty = bar_length - filled
    
    if style == 'rainbow':
        rainbow_colors = ['🟦', '🟩', '🟨', '🟧', '🟥']
        filled_bar = ''.join([rainbow_colors[i % len(rainbow_colors)] for i in range(filled)])
        empty_bar = '⚪' * empty
        return filled_bar + empty_bar
    
    elif style == 'fire':
        fire_colors = ['🔴', '🟠', '🟡', '🟧']
        filled_bar = ''.join([fire_colors[min(int(i * len(fire_colors) / filled), len(fire_colors)-1)] 
                              for i in range(filled)]) if filled > 0 else ''
        empty_bar = '⚫' * empty
        return filled_bar + empty_bar
    
    elif style == 'ice':
        ice_colors = ['🔵', '💙', '🟦']
        filled_bar = ''.join([ice_colors[min(int(i * len(ice_colors) / filled), len(ice_colors)-1)] 
                              for i in range(filled)]) if filled > 0 else ''
        empty_bar = '⚪' * empty
        return filled_bar + empty_bar
    
    elif style == 'neon':
        if current_time is None:
            current_time = time.time()
        animation_frame = int(current_time * 3) % 2
        neon_char = '🟪' if animation_frame == 0 else '🟩'
        filled_bar = neon_char * filled
        empty_bar = '⬛' * empty
        return filled_bar + empty_bar
    
    elif style == 'tech':
        filled_bar = '▓' * filled
        empty_bar = '░' * empty
        return filled_bar + empty_bar
    
    elif style == 'animated':
        animation_chars = ['▰', '▱', '▲', '▼']
        frame = int((current_time or time.time()) * 4) % len(animation_chars)
        filled_bar = animation_chars[frame] * filled
        empty_bar = '▱' * empty
        return filled_bar + empty_bar
    
    else:
        # Default fire theme
        return '🟧' * filled + '🔸' * empty


def create_animated_spinner(current_time=None):
    """Create an animated spinner for download/upload"""
    if current_time is None:
        current_time = time.time()
    
    spinners = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    frame = int(current_time * 10) % len(spinners)
    return spinners[frame]


def get_animated_emoji(operation, current_time=None):
    """Get animated emoji for download/upload operations"""
    if current_time is None:
        current_time = time.time()
    
    if "Download" in operation:
        download_animation = ['📥️', '⬇️', '📥️']
        frame = int(current_time * 2) % len(download_animation)
        return download_animation[frame]
    elif "Upload" in operation:
        upload_animation = ['📤️', '⬆️', '📤️']
        frame = int(current_time * 2) % len(upload_animation)
        return upload_animation[frame]
    else:
        processing_animation = ['🔄', '⟳', '🔃', '↻']
        frame = int(current_time * 1.5) % len(processing_animation)
        return processing_animation[frame]


def generate_animated_progress_ui(current, total, operation, filename, start_time, style='rainbow'):
    """
    Generate an animated and colorful progress message
    
    Args:
        current: Current bytes downloaded/uploaded
        total: Total bytes to download/upload
        operation: "Downloading" or "Uploading"
        filename: Name of the file being transferred
        start_time: Start time of the transfer
        style: Progress bar style ('rainbow', 'fire', 'ice', 'neon', 'tech', 'animated')
    
    Returns:
        Formatted progress message string with animations
    """
    
    now = time.time()
    elapsed = now - start_time if start_time else 1
    percentage = 0 if total == 0 else (current * 100) / total
    speed = current / elapsed if elapsed > 0 else 0
    
    # Calculate ETA
    if speed > 0:
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
    else:
        eta_seconds = 0
    
    # Get animated elements
    spinner = create_animated_spinner(now)
    op_emoji, op_text = format_operation_type(operation)
    animated_op_emoji = get_animated_emoji(operation, now)
    file_emoji, file_type = get_file_type_emoji(filename)
    
    # Create colorful progress bar
    progress_bar = create_colorful_progress_bar(current, total, 15, style, now)
    
    # Format sizes and speeds
    current_text = humanbytes(current)
    total_text = humanbytes(total)
    speed_text = humanbytes(speed)
    
    # Format times
    elapsed_str = convert_seconds(elapsed)
    eta_str = convert_seconds(eta_seconds) if eta_seconds > 0 else "∞"
    
    # Determine bar animation based on percentage
    if percentage >= 100:
        status_indicator = "✅ COMPLETE!"
        bar_animation = "🟩" * 15
    elif percentage >= 75:
        status_indicator = "🔥 ALMOST DONE"
        bar_animation = progress_bar
    elif percentage >= 50:
        status_indicator = "⚡ HALFWAY THERE"
        bar_animation = progress_bar
    elif percentage >= 25:
        status_indicator = "📊 IN PROGRESS"
        bar_animation = progress_bar
    else:
        status_indicator = "🚀 STARTING"
        bar_animation = progress_bar
    
    # Build the animated message
    message = (
        f"{spinner} {animated_op_emoji} **{op_text} In Progress** {spinner}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"📂 File: `{filename}`\n"
        f"🎯 Type: {file_type}\n"
        f"\n"
        f"{bar_animation}\n"
        f"**{percentage:.1f}%** • {status_indicator}\n"
        f"\n"
        f"📊 **Stats:**\n"
        f"   ⚡ Speed: `{speed_text}/s`\n"
        f"   📦 Progress: `{current_text} / {total_text}`\n"
        f"   ⏳ Elapsed: `{elapsed_str}`\n"
        f"   ⏱️  ETA: `{eta_str}`\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ **RADHEY** • Safe Content Manager ⚡"
    )
    
    return message


def generate_super_animated_progress_ui(current, total, operation, filename, start_time):
    """
    Ultra-animated version with gradient bars and real-time animation
    """
    now = time.time()
    elapsed = now - start_time if start_time else 1
    percentage = 0 if total == 0 else (current * 100) / total
    speed = current / elapsed if elapsed > 0 else 0
    
    # Calculate ETA
    if speed > 0:
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
    else:
        eta_seconds = 0
    
    # Get animated elements
    spinner = create_animated_spinner(now)
    op_emoji, op_text = format_operation_type(operation)
    
    # Create gradient bar that changes with percentage
    if percentage < 33:
        colors = '🔵🔵🔵🔵🔵⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫'
    elif percentage < 66:
        colors = '🟡🟡🟡🟡🟡🟡🟡🟡⚫⚫⚫⚫⚫⚫⚫'
    else:
        colors = '🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢⚫⚫⚫⚫⚫'
    
    filled = int(15 * percentage / 100)
    bar = colors[:filled] + ('⚫' * (15 - filled))
    
    # Format sizes and speeds
    current_text = humanbytes(current)
    total_text = humanbytes(total)
    speed_text = humanbytes(speed)
    
    # Format times
    elapsed_str = convert_seconds(elapsed)
    eta_str = convert_seconds(eta_seconds) if eta_seconds > 0 else "⏳"
    
    # Blocks for visual indication
    blocks = int(percentage / 10)
    visual_blocks = '█' * blocks + '░' * (10 - blocks)
    
    message = (
        f"{spinner} **{op_text}** • {spinner}\n"
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ {visual_blocks} {percentage:.1f}%\n"
        f"┃ {bar}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"\n"
        f"📄 `{filename}`\n"
        f"⚡ {speed_text}/s | 📦 {current_text}/{total_text}\n"
        f"⏱️  {elapsed_str} elapsed | 🕐 {eta_str} remaining\n"
    )
    
    return message
