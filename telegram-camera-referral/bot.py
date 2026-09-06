import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "770098764"))
BASE_URL = os.getenv(
    "BASE_URL",
    "https://whatsapp-bot-v1-5.onrender.com"
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    user = message.from_user

    user_id = user.id
    username = user.username or "بدون username"
    name = user.full_name

    referral_link = f"{BASE_URL}/?q={user_id}"

    await message.answer(
        f"👋 أهلاً {name}\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Username: @{username}\n\n"
        f"🔗 رابطك الخاص:\n"
        f"{referral_link}"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
