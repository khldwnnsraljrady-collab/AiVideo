from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="Telegram Referral Camera")


@app.get("/", response_class=HTMLResponse)
async def home(q: str = Query(default="")):
    if not q:
        return """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>التسجيل</title>
        </head>
        <body>
            <h2>الرابط غير صحيح</h2>
            <p>يجب فتح رابط إحالة صالح.</p>
        </body>
        </html>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>التسجيل</title>
    </head>
    <body>
        <h2>مرحبًا بك</h2>
        <p>تم فتح الرابط الخاص بالمستخدم:</p>
        <p><strong>{q}</strong></p>

        <p>
            في الخطوة التالية سنضيف هنا واجهة الكاميرا
            بعد الحصول على إذن المستخدم.
        </p>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok"}
