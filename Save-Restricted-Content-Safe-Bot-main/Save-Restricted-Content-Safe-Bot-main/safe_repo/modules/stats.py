#safe_repo

from datetime import datetime, timezone

from safe_repo import app
from pyrogram import filters
from config import OWNER_ID
from safe_repo.core.mongo.users_db import get_users, add_user, get_user
from safe_repo.core.mongo.plans_db import premium_users




@app.on_message(group=10)
async def chat_watcher_func(_, message):
    try:
        if message.from_user:
            us_in_db = await get_user(message.from_user.id)
            if not us_in_db:
                await add_user(message.from_user.id)
    except:
        pass


@app.on_message(filters.command("stats"))
async def stats(client, message):
    users = len(await get_users())
    premium = await premium_users()
    await message.reply_text(f"""
**Total Stats of** {(await client.get_me()).mention} :

**Total Users** : {users}
**Premium Users** : {len(premium)}

**__Powered by safe_repo__**
""")

    # MongoDB analytics are best-effort; the reply above already succeeded so
    # any failure here must not raise into the handler.
    try:
        from safe_repo.core.mongo import analytics_db, download_stats, quota_db
        user_id = message.from_user.id if message.from_user else 0

        summary = await analytics_db.get_analytics_summary(days=30)
        top = await download_stats.get_top_downloads(limit=10)
        quota = await quota_db.get_user_quota(user_id)

        lines = ["**📈 Usage (last 30 days)**", f"**Events** : {summary.get('total_events', 0)}"]
        for event_type, count in sorted(
            (summary.get("by_type") or {}).items(), key=lambda item: item[1], reverse=True
        )[:5]:
            lines.append(f"• `{event_type}` — {count}")

        if top:
            lines += ["", "**🔥 Top Downloads**"]
            for index, entry in enumerate(top, 1):
                title = (entry.get("title") or entry.get("token") or "unknown")[:40]
                lines.append(f"{index}. {title} — {entry.get('views', 0)} views")

        if quota:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            month = datetime.now(timezone.utc).strftime("%Y-%m")
            daily_used = (quota.get("daily") or {}).get(today, 0)
            monthly_used = (quota.get("monthly") or {}).get(month, 0)
            lines += [
                "",
                "**🧾 Your Quota**",
                f"**Daily** : {daily_used}/{quota.get('daily_limit', 0)}",
                f"**Monthly** : {monthly_used}/{quota.get('monthly_limit', 0)}",
            ]

        await message.reply_text("\n".join(lines))
    except Exception as error:
        await message.reply_text(f"⚠️ Analytics unavailable: {error}")
  
