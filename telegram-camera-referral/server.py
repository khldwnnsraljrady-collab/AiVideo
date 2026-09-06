from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Telegram Referral Camera")

templates = Jinja2Templates(directory="templates")


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
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
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


@app.get("/health")
async def health():
    return {"status": "ok"}
