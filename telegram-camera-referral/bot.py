import os
import json
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(
    os.getenv("ADMIN_TELEGRAM_ID", "770098764")
)

BASE_URL = os.getenv(
    "BASE_URL",
    "https://aivideo-wn1o.onrender.com"
)

USERS_FILE = Path("users.json")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def load_users():
    if not USERS_FILE.exists():
        return {
            "users": {},
            "total_users": 0
        }

    try:
        with USERS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return {
            "users": {},
            "total_users": 0
        }


def save_users(data):
    with USERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


@dp.message(CommandStart())
async def start_handler(message: Message):
    user = message.from_user

    user_id = str(user.id)
    username = user.username or ""
    name = user.full_name

    data = load_users()

    is_new_user = user_id not in data["users"]

    if is_new_user:
        data["users"][user_id] = {
            "name": name,
            "username": username,
            "telegram_id": user.id,
            "referrals": 0
        }

        data["total_users"] += 1

        save_users(data)

    referral_link = f"{BASE_URL}/?q={user.id}"

    username_text = (
        f"@{username}"
        if username
        else "بدون username"
    )

    await message.answer(
        f"👋 أهلاً بك {name}\n\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Username: {username_text}\n\n"
        f"🔗 رابطك الخاص:\n"
        f"{referral_link}\n\n"
        f"👥 عدد الأشخاص الذين استخدموا رابطك: "
        f"{data['users'][user_id]['referrals']}"
    )


async def main():
    await dp.start_polling(
        bot,
        handle_signals=False
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
