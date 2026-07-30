import pytz
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, OWNER_ID

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URL) if MONGO_URL else None
        self.db = self.client.titubot if self.client else None
        self.users = self.db.premium_users if self.db is not None else None
        self.settings = self.db.settings if self.db is not None else None

    # --- DYNAMIC SETTINGS MANAGEMENT ---
    async def get_setting(self, key: str, default=None):
        if self.settings is None: 
            return default
        data = await self.settings.find_one({"_id": key})
        return data["value"] if data else default

    async def set_setting(self, key: str, value):
        if self.settings is None: 
            return
        await self.settings.update_one(
            {"_id": key},
            {"$set": {"value": value}},
            upsert=True
        )

    async def get_sudo_users(self) -> list:
        sudos = await self.get_setting("sudo_users", [])
        if OWNER_ID not in sudos and OWNER_ID != 0:
            sudos.append(OWNER_ID)
        return sudos

    async def add_sudo(self, user_id: int):
        sudos = await self.get_sudo_users()
        if user_id not in sudos:
            sudos.append(user_id)
            await self.set_setting("sudo_users", sudos)

    async def remove_sudo(self, user_id: int):
        sudos = await self.get_sudo_users()
        if user_id in sudos and user_id != OWNER_ID:
            sudos.remove(user_id)
            await self.set_setting("sudo_users", sudos)

    # --- PREMIUM USERS MANAGEMENT ---
    async def add_premium(self, user_id: int, expire_date: datetime.datetime):
        if self.users is None: 
            return
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"expire_date": expire_date}},
            upsert=True
        )

    async def remove_premium(self, user_id: int):
        if self.users is None: 
            return
        await self.users.delete_one({"_id": user_id})

    async def is_premium(self, user_id: int) -> bool:
        sudos = await self.get_sudo_users()
        if user_id in sudos: 
            return True
        if self.users is None: 
            return True
        
        data = await self.users.find_one({"_id": user_id})
        if not data or "expire_date" not in data:
            return False
        return data["expire_date"] > datetime.datetime.now(pytz.UTC)

db = Database()