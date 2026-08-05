"""
Main entry point to launch FastAPI REST API and Telegram Bot polling concurrently.
"""

import asyncio
import logging
import os
import uvicorn

from api import app, repo, _add_cors_middleware
from bot_service import start_bot_polling

# Ensure CORS middleware is attached (idempotent) using configured origin whitelist.
_add_cors_middleware(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("saas_main")


async def run_services():
    bot, dp = await start_bot_polling()
    log.info("Starting @vacancy_spott_bot polling...")
    
    # Run Uvicorn server in background task using PORT and HOST from environment (Render compatibility)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    
    server_task = asyncio.create_task(server.serve())
    polling_task = asyncio.create_task(dp.start_polling(bot))

    tasks = [server_task, polling_task]
    try:
        from telethon_parser import start_parser
        parser_task = asyncio.create_task(start_parser())
        tasks.append(parser_task)
        log.info("📡 Telethon Channel Parser integrated & started.")
    except Exception as exc:
        log.warning("Could not start Telethon parser in server.py: %s", exc)

    log.info("🚀 Vacancy Spotter SaaS Backend & Bot started successfully!")
    log.info(f"📱 Mini App Web Cabinet available at: http://{host}:{port}/app")
    
    try:
        await asyncio.gather(*tasks)
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(run_services())

