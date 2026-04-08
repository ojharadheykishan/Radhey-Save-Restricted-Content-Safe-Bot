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
