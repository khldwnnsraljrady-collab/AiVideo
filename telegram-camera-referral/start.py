import asyncio
import threading
import uvicorn

from bot import main as bot_main


def run_bot():
    asyncio.run(bot_main())


if __name__ == "__main__":
    bot_thread = threading.Thread(
        target=run_bot,
        daemon=True
    )

    bot_thread.start()

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000
    )
