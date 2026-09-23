#safe_repo

from datetime import timedelta
import pytz
import datetime, time
from safe_repo import app
from config import OWNER_ID
from safe_repo.core.func import get_seconds
from safe_repo.core.mongo import plans_db
from pyrogram import filters



@app.on_message(filters.command("rem") & filters.user(OWNER_ID))
async def remove_premium(client, message):
    if len(message.command) == 2:
        user_id = int(message.command[1])  
        user = await client.get_users(user_id)
        data = await plans_db.check_premium(user_id)  
        
        if data and data.get("_id"):
            await plans_db.remove_premium(user_id)
            await message.reply_text("ᴜꜱᴇʀ ʀᴇᴍᴏᴠᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ !")
            await client.send_message(
                chat_id=user_id,
                text=f"<b>ʜᴇʏ {user.mention},\n\nʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇss ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.\nᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴜsɪɴɢ ᴏᴜʀ sᴇʀᴠɪᴄᴇ 😊.</b>"
            )
        else:
            await message.reply_text("ᴜɴᴀʙʟᴇ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴜꜱᴇᴅ !\nᴀʀᴇ ʏᴏᴜ ꜱᴜʀᴇ, ɪᴛ ᴡᴀꜱ ᴀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ɪᴅ ?")
    else:
        await message.reply_text("ᴜꜱᴀɢᴇ : /rem user_id") 



@app.on_message(filters.command("myplan"))
async def myplan(client, message):
    user_id = message.from_user.id
    user = message.from_user.mention
    data = await plans_db.check_premium(user_id)  
    if data:
        # Check if it's lifetime premium (expire_date is None)
        if data.get("expire_date") is None:
            await message.reply_text(f"⚜️ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ᴅᴀᴛᴀ :\n\n👤 ᴜꜱᴇʀ : {user}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴍᴇᴍʙᴇʀꜱʜɪᴘ : **Lifetime Premium**\n\n🎉 You have lifetime access to all premium features!")
        elif data.get("expire_date"):
            expiry = data.get("expire_date")
            expiry_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata"))
            expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")            
            
            current_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            time_left = expiry_ist - current_time
                
            
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
                
            
            time_left_str = f"{days} ᴅᴀʏꜱ, {hours} ʜᴏᴜʀꜱ, {minutes} ᴍɪɴᴜᴛᴇꜱ"
            await message.reply_text(f"⚜️ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ᴅᴀᴛᴀ :\n\n👤 ᴜꜱᴇʀ : {user}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴛɪᴍᴇ ʟᴇꜰᴛ : {time_left_str}\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}")   
    else:
        await message.reply_text(f"ʜᴇʏ {user},\n\nʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴀɴʏ ᴀᴄᴛɪᴠᴇ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs")
        


@app.on_message(filters.command("check") & filters.user(OWNER_ID))
async def get_premium(client, message):
    if len(message.command) == 2:
        user_id = int(message.command[1])
        user = await client.get_users(user_id)
        data = await plans_db.check_premium(user_id)  
        if data:
            # Check if it's lifetime premium (expire_date is None)
            if data.get("expire_date") is None:
                await message.reply_text(f"⚜️ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ᴅᴀᴛᴀ :\n\n👤 ᴜꜱᴇʀ : {user.mention}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴍᴇᴍʙᴇʀꜱʜɪᴘ : **Lifetime Premium**\n\n🎉 This user has lifetime access to all premium features!")
            elif data.get("expire_date"):
                expiry = data.get("expire_date") 
                expiry_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata"))
                expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")            
                
                current_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
                time_left = expiry_ist - current_time
                
                
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                
                time_left_str = f"{days} days, {hours} hours, {minutes} minutes"
                await message.reply_text(f"⚜️ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ᴅᴀᴛᴀ :\n\n👤 ᴜꜱᴇʀ : {user.mention}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴛɪᴍᴇ ʟᴇꜰᴛ : {time_left_str}\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}")
        else:
            await message.reply_text("ɴᴏ ᴀɴʏ ᴘʀᴇᴍɪᴜᴍ ᴅᴀᴛᴀ ᴏꜰ ᴛʜᴇ ᴡᴀꜱ ꜰᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ !")
    else:
        await message.reply_text("ᴜꜱᴀɢᴇ : /check user_id")


@app.on_message(filters.command("add") & filters.user(OWNER_ID))
async def give_premium_cmd_handler(client, message):
    if len(message.command) == 4:
        time_zone = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        current_time = time_zone.strftime("%d-%m-%Y\n⏱️ ᴊᴏɪɴɪɴɢ ᴛɪᴍᴇ : %I:%M:%S %p") 
        user_id = int(message.command[1])
        user = await client.get_users(user_id)
        time = message.command[2]+" "+message.command[3]
        seconds = await get_seconds(time)
        if seconds > 0:
            expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)  
            plan_type = "15_days" if message.command[2:4] == ["15", "days"] else "time_limited"
            await plans_db.add_premium(user_id, expiry_time, plan_type=plan_type)
            data = await plans_db.check_premium(user_id)
            expiry = data.get("expire_date")   
            expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")         
            await message.reply_text(f"ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅\n\n👤 ᴜꜱᴇʀ : {user.mention}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time}</code>\n\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist} \n\n__**Powered by safe_repo__**", disable_web_page_preview=True)
            await client.send_message(
                chat_id=user_id,
                text=f"👋 ʜᴇʏ {user.mention},\nᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴘᴜʀᴄʜᴀꜱɪɴɢ ᴘʀᴇᴍɪᴜᴍ.\nᴇɴᴊᴏʏ !! ✨🎉\n\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time}</code>\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True              
            )    
#            await client.send_message(PREMIUM_LOGS, text=f"#Added_Premium\n\n👤 ᴜꜱᴇʀ : {user.mention}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time}</code>\n\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True)
                    
        else:
            await message.reply_text("Invalid time format. Please use '1 day for days', '1 hour for hours', or '1 min for minutes', or '1 month for months' or '1 year for year'")
    else:
        await message.reply_text("Usage : /add user_id time (e.g., '1 day for days', '1 hour for hours', or '1 min for minutes', or '1 month for months' or '1 year for year')")


async def _format_plan_users(client, title, users, include_expiry=False):
    """Format a compact admin report without failing on deleted Telegram users."""
    if not users:
        return f"{title}\n\nNo users found."

    lines = [title, ""]
    for index, entry in enumerate(users, 1):
        user_id = entry if isinstance(entry, int) else entry["user_id"]
        try:
            user = await client.get_users(user_id)
            display_name = user.mention
        except Exception:
            display_name = f"User {user_id}"
        line = f"{index}. {display_name} (ID: {user_id})"
        if include_expiry and isinstance(entry, dict):
            line += f" - Expires: {entry.get('expire_date', 'unknown')}"
        lines.append(line)
    return "\n".join(lines)


@app.on_message(filters.command("plan") & filters.user(OWNER_ID))
async def plan_management_command(client, message):
    """Show premium plan reports for administrators."""
    await plans_db.check_and_remove_expired_users()
    command_args = [argument.lower() for argument in message.command[1:]]
    lifetime = await plans_db.get_lifetime_users()
    one_day = await plans_db.get_1_day_users()
    fifteen_day = await plans_db.get_15_day_users()
    time_limited = await plans_db.get_time_limited_users()

    if not command_args or command_args[0] in ("help", "summary"):
        await message.reply_text(
            "📊 Premium plan summary\n\n"
            f"Lifetime users: {len(lifetime)}\n"
            f"1-day trial users: {len(one_day)}\n"
            f"15-day users: {len(fifteen_day)}\n"
            f"Other time-limited users: {len(time_limited) - len(fifteen_day) - len(one_day)}\n"
            f"Active premium users: {len(lifetime) + len(time_limited)}\n\n"
            "Commands:\n"
            "/plan lifetime\n"
            "/plan 1day\n"
            "/plan 15days\n"
            "/plan active\n"
            "/plan user <user_id>"
        )
        return

    report_type = command_args[0]
    if report_type == "lifetime":
        await message.reply_text(await _format_plan_users(client, "⚜️ Lifetime premium users", lifetime))
    elif report_type in ("1day", "1-day", "trial"):
        await message.reply_text(await _format_plan_users(client, "🎁 1-day trial users", one_day, include_expiry=True))
    elif report_type in ("15days", "15day"):
        await message.reply_text(await _format_plan_users(client, "⏰ 15-day plan users", fifteen_day, include_expiry=True))
    elif report_type == "active":
        active_users = [
            {"user_id": user_id, "plan_type": "lifetime", "expire_date": None}
            for user_id in lifetime
        ] + time_limited
        await message.reply_text(await _format_plan_users(client, "✅ Active premium users", active_users, include_expiry=True))
    elif report_type == "user" and len(command_args) == 2:
        try:
            user_id = int(command_args[1])
        except ValueError:
            await message.reply_text("Usage: /plan user <numeric_user_id>")
            return
        premium_data = await plans_db.check_premium(user_id)
        if not premium_data:
            await message.reply_text(f"No active premium plan found for user {user_id}.")
            return
        plan_name = "Lifetime" if premium_data.get("expire_date") is None else "Time-limited"
        await message.reply_text(
            f"👤 User ID: {user_id}\n"
            f"Plan: {plan_name}\n"
            f"Expires: {premium_data.get('expire_date') or 'Never'}"
        )
    else:
        await message.reply_text("Usage: /plan, /plan lifetime, /plan 1day, /plan 15days, /plan active, /plan user <user_id>")


@app.on_message(filters.command("lifetime") & filters.user(OWNER_ID))
async def lifetime_users(client, message):
    users = await plans_db.get_lifetime_users()
    if not users:
        await message.reply_text("कोई लिफ़्टाइम प्रीमियम यूज़र नहीं हैं।")
        return
    text = "⚜️ **लिफ़्टाइम प्रीमियम यूज़र्स / Lifetime Premium Users**\n\n"
    for i, uid in enumerate(users, 1):
        try:
            user = await client.get_users(uid)
            mention = user.mention
        except Exception:
            mention = f"<code>{uid}</code>"
        text += f"{i}. {mention} (ID: <code>{uid}</code>)\n"
    await message.reply_text(text)


@app.on_message(filters.command("timelimit") & filters.user(OWNER_ID))
async def time_limited_users(client, message):
    users = await plans_db.get_time_limited_users()
    if not users:
        await message.reply_text("कोई टाइम-लिमिटेड प्लान वाला यूज़र नहीं हैं।")
        return
    text = "⏰ **टाइम-लिमिटेड प्लान यूज़र्स / Time-Limited Plan Users**\n\n"
    for i, entry in enumerate(users, 1):
        uid = entry["user_id"]
        try:
            user = await client.get_users(uid)
            mention = user.mention
        except Exception:
            mention = f"<code>{uid}</code>"
        expiry = entry["expire_date"]
        text += f"{i}. {mention} (ID: <code>{uid}</code> - Expires: <code>{expiry}</code>)\n"
    await message.reply_text(text)


@app.on_message(filters.command("active") & filters.user(OWNER_ID))
async def active_members(client, message):
    await plans_db.check_and_remove_expired_users()
    details = await plans_db.get_all_premium_details()
    if not details:
        await message.reply_text("कोई एक्टिव प्रीमियम मंबर नहीं हैं।")
        return
    lifetime = [d for d in details if d["plan_type"] == "lifetime"]
    time_limited = [d for d in details if d["plan_type"] != "lifetime"]
    text = "✅ **एक्टिव प्रीमियम मंबर्स / Active Premium Members**\n\n"
    text += f"⚜️ लिफ़्टाइम: {len(lifetime)}\n"
    text += f"⏰ टाइम-लिमिटेड: {len(time_limited)}\n"
    text += f"📊 कुल: {len(details)}\n\n"
    for i, d in enumerate(time_limited, 1):
        uid = d["user_id"]
        try:
            user = await client.get_users(uid)
            mention = user.mention
        except Exception:
            mention = f"<code>{uid}</code>"
        expiry = d["expire_date"]
        text += f"{i}. {mention} (ID: <code>{uid}</code> - Expires: <code>{expiry}</code>)\n"
    await message.reply_text(text)

  
