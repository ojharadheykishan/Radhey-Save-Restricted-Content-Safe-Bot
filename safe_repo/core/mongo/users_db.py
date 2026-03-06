#safe_repo

from config import MONGO_DB
from motor.motor_asyncio import AsyncIOMotorClient as MongoCli


# Check if MONGO_DB is provided
if MONGO_DB:
    try:
        mongo = MongoCli(MONGO_DB)
        db = mongo.users
        db = db.users_db
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        mongo = None
else:
    mongo = None


async def get_users():
    # If MongoDB is not connected, return empty list
    if not mongo:
        return []
    
    user_list = []
    try:
        async for user in db.users.find({"user": {"$gt": 0}}):
            user_list.append(user['user'])
    except Exception as e:
        print(f"Error getting users from MongoDB: {e}")
    return user_list


async def get_user(user):
    users = await get_users()
    if user in users:
        return True
    else:
        return False

async def add_user(user):
    if not mongo:
        return
    
    users = await get_users()
    if user in users:
        return
    try:
        await db.users.insert_one({"user": user})
    except Exception as e:
        print(f"Error adding user to MongoDB: {e}")


async def del_user(user):
    if not mongo:
        return
    
    users = await get_users()
    if not user in users:
        return
    try:
        await db.users.delete_one({"user": user})
    except Exception as e:
        print(f"Error deleting user from MongoDB: {e}")
