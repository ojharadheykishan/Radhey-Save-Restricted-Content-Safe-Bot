#safe_repo

# ------------------------------------------------------------ #

START_TXT = """
Hi, welcome to Advance Content Saver Bot, designed to save restricted messages from public/private channels and private groups. First login in bot by /login then send post link.
"""

# Motivational quotes related to study (Hindi and English)
MOTIVATIONAL_QUOTES = [
    # English
    "The only way to do great work is to love what you do. - Steve Jobs",
    "Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
    "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
    "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
    "Believe you can and you're halfway there. - Theodore Roosevelt",
    "Education is the passport to the future, for tomorrow belongs to those who prepare for it today. - Malcolm X",
    "The secret of getting ahead is getting started. - Mark Twain",
    "Every strike brings me closer to the next home run. - Babe Ruth",
    "Hardships often prepare ordinary people for an extraordinary destiny. - C.S. Lewis",
    "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
    
    # Hindi
    "जीवन में सफलता का कोई ईश्वर नहीं होता, केवल एक कोशिश करने वाला होता है।",
    "अपने लक्ष्य की ओर बढ़ते रहो, चाहे रास्ता कितना ही कठिन क्यों न हो।",
    "सफलता का मार्ग कभी भी सीधा नहीं होता, इसे प्राप्त करने के लिए मेहनत करनी पड़ती है।",
    "हर सुबह एक नया अवसर होता है, एक नई कोशिश करने का।",
    "ज्ञान का समुद्र कभी नहीं खत्म होता, जितना आप जानते हैं, उतना ही कम होता है।",
    "किसी भी काम को पूरा करने के लिए दृढ़ता और लगन होनी चाहिए।",
    "सफलता नहीं, प्रयास ही सबसे बड़ी जीत है।",
    "आपका विद्यार्थी जीवन आपके भविष्य का निर्माण करता है, इसे सजा कर रखें।",
    "हर दिन थोड़ी सी प्रगति, एक दिन बहुत बड़ा परिवर्तन ला देगी।",
    "विद्या देने वाले को देवता की तरह पूजा जाता है, क्योंकि वो भविष्य को सजाते हैं।"
]

FORCE_MSG = """
Hey {},

According to my database, you've not joined the updates channel yet. If you want to use me, then join the updates channel and start me again!
"""

HELP_TXT = """
HELP SECTION 📝

🛠️ /settings - Open settings to set your requirements.

🔒 /login - Login to your userbot session.

📦 /batch - Download bulk links in a systematic way.

⛔ /cancel - Stop batch processing.
"""

HELP2_TXT = """
🕵️ Help:

FOR PUBLIC AND PRIVATE CHANNEL OR GROUP:
- First, log in.
- Then send the message link of any channel that you've joined in your login account.

FOR BOT:
- Send the link in this format: https://t.me/b/bot_username/message_id (use Plus Messenger for message_id)

FOR GROUP TOPIC:
- (For Private Group) Group topic link is like: https://t.me/c/xxxxxxxxx/first_id/second_id
But, send it like this: https://t.me/c/xxxxxxx/second_id (remove first id and one /)
- (For Public Group) Follow the private link step but remove "/c" from the link. Ex - https://t.me/username/second_id

#FAQ:

- If the bot says "Have you joined the channel?" then just log in again to the bot and try.

- If your batch is stuck, then use /stop.
"""

ADMIN_TXT = """
ADMINS PANEL 🛠️

➕ /add - Add user ID to the premium section.

➖ /rem - Remove user ID from the premium section.

🔍 /check - Check if a user ID is in the premium section.

📢 /broadcast - Broadcast a message without a forward tag.

📣 /announce - Broadcast a message with a forward tag.

📊 /stats - Check your bot's stats.
"""

SETTINGS_TXT = """
Welcome to the settings section. Here, you can choose button: caption or session and thumbnail.
"""

CAPTI0NS_TXT = """
Customize the bot's caption here to tailor it to your preferences and needs!
"""

THUMBNAIL_TXT = """
Customize the bot's thumbnail here to tailor it to your preferences and needs!
"""

SESSION_TXT = """
Customize the bot's session here to tailor it to your preferences and needs!
"""

CHANNEL_TXT = """
Customize the bot's channel here to tailor it to your preferences and needs!
"""
