#!/usr/bin/env python3
"""
Test script for RADHEY Beautiful Progress UI
Demonstrates the progress messages without needing a running bot
"""

import sys
import time
sys.path.insert(0, '/workspaces/Radhey-Save-Restricted-Content-Safe-Bot')

from safe_repo.core.progress_ui import (
    generate_progress_ui,
    generate_compact_progress_ui,
    create_fire_progress_bar,
    get_file_type_emoji
)


def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_progress_ui():
    """Test the beautiful progress UI"""
    
    print_section("🎬 RADHEY Beautiful Progress UI Test")
    
    # Test 1: Video Download at 25%
    print("\n📥 TEST 1: Video Download (25% Complete)")
    print("-" * 60)
    current = 275_000_000  # 275 MB
    total = 1_100_000_000  # 1.1 GB
    start_time = time.time() - 60  # 1 minute elapsed
    
    msg = generate_progress_ui(current, total, "Downloading", "Money_Heist_S05_E10.mkv", start_time)
    print(msg)
    
    # Test 2: Video Download at 65%
    print("\n📥 TEST 2: Video Download (65% Complete)")
    print("-" * 60)
    current = 715_000_000  # 715 MB
    total = 1_100_000_000  # 1.1 GB
    start_time = time.time() - 135  # 2m 15s elapsed
    
    msg = generate_progress_ui(current, total, "Downloading", "Money_Heist_S05_E10.mkv", start_time)
    print(msg)
    
    # Test 3: Video Upload at 90%
    print("\n📤 TEST 3: Video Upload (90% Complete)")
    print("-" * 60)
    current = 990_000_000  # 990 MB
    total = 1_100_000_000  # 1.1 GB
    start_time = time.time() - 300  # 5 minutes elapsed
    
    msg = generate_progress_ui(current, total, "Uploading", "presentation.mp4", start_time)
    print(msg)
    
    # Test 4: Document Upload at 40%
    print("\n📤 TEST 4: PDF Document Upload (40% Complete)")
    print("-" * 60)
    current = 40_000_000  # 40 MB
    total = 100_000_000  # 100 MB
    start_time = time.time() - 45  # 45 seconds elapsed
    
    msg = generate_progress_ui(current, total, "Uploading", "report.pdf", start_time)
    print(msg)
    
    # Test 5: Audio Download at 50%
    print("\n📥 TEST 5: Audio Download (50% Complete)")
    print("-" * 60)
    current = 150_000_000  # 150 MB
    total = 300_000_000  # 300 MB
    start_time = time.time() - 90  # 1m 30s elapsed
    
    msg = generate_progress_ui(current, total, "Downloading", "album_collection.zip", start_time)
    print(msg)
    
    # Test 6: Compact UI version
    print("\n📤 TEST 6: Compact Version (Mobile-Friendly)")
    print("-" * 60)
    current = 512_000_000  # 512 MB
    total = 1_024_000_000  # 1 GB
    start_time = time.time() - 120  # 2 minutes elapsed
    
    msg = generate_compact_progress_ui(current, total, "Uploading", "large_file.zip", start_time)
    print(msg)
    
    # Test 7: File type detection showcase
    print("\n\n🎨 TEST 7: File Type Detection")
    print("-" * 60)
    
    test_files = [
        "movie.mp4",
        "song.mp3",
        "document.pdf",
        "photo.jpg",
        "archive.zip",
        "code.py",
        "unknown.xyz"
    ]
    
    print(f"{'Filename':<25} | {'Emoji':<6} | {'Type':<15}")
    print("-" * 50)
    
    for filename in test_files:
        emoji, file_type = get_file_type_emoji(filename)
        print(f"{filename:<25} | {emoji:<6} | {file_type:<15}")
    
    # Test 8: Fire progress bar showcase
    print("\n\n🔥 TEST 8: Fire Progress Bar Showcase")
    print("-" * 60)
    
    percentages = [0, 10, 25, 50, 75, 90, 100]
    
    for percent in percentages:
        current = percent
        total = 100
        bar = create_fire_progress_bar(current, total, 10)
        padding = " " * (3 - len(str(percent)))
        print(f"[{padding}{percent}%] {bar}")
    
    print_section("✅ All Tests Completed!")
    print("\n💡 Integration Status:")
    print("   ✓ Progress UI module loaded successfully")
    print("   ✓ File type detection working")
    print("   ✓ Progress bar generation working")
    print("   ✓ Ready for bot integration!")
    print("\n📝 Next Steps:")
    print("   1. Run your bot: python3 -m safe_repo")
    print("   2. Download/Upload media to see the beautiful progress!")
    print("   3. Check safe_repo/core/progress_ui.py for customization")
    print()


if __name__ == "__main__":
    try:
        test_progress_ui()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
