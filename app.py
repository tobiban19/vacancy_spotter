import asyncio
import os
import sys
import threading
import gradio as gr
import uvicorn

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from api import app, repo, _add_cors_middleware
from bot_service import start_bot_polling

# Ensure CORS middleware is attached (idempotent) using configured origin whitelist.
_add_cors_middleware(app)

def start_services_in_thread():
    async def run_services():
        bot, dp = await start_bot_polling()
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)

        server_task = asyncio.create_task(server.serve())
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

        tasks = [server_task, polling_task]

        # Start Telethon Channel Parser (MTProto listener for vacancy channels)
        try:
            from telethon_parser import start_parser
            parser_task = asyncio.create_task(start_parser())
            tasks.append(parser_task)
            print("📡 Telethon Channel Parser integrated & started.")
        except Exception as exc:
            print(f"⚠️ Could not start Telethon parser: {exc}")

        print("🚀 Vacancy Spotter SaaS Backend & Bot started in Gradio Space!")
        try:
            await asyncio.gather(*tasks)
        finally:
            await repo.close()

    asyncio.run(run_services())

# Start Python Telegram Bot & FastAPI in a background daemon thread
t = threading.Thread(target=start_services_in_thread, daemon=True)
t.start()

# Build Gradio UI for Hugging Face Spaces status display
with gr.Blocks(title="Vacancy Spotter SaaS") as demo:
    gr.Markdown("# 🚀 Vacancy Spotter SaaS Backend & Bot")
    gr.Markdown("✅ Telegram Bot `@vacancy_spott_bot` is running 24/7 in background!")
    gr.Markdown("📱 **Mini App Web Cabinet**: [https://frontend-psi-nine-2ydjpsdrfq.vercel.app](https://frontend-psi-nine-2ydjpsdrfq.vercel.app)")

if __name__ == "__main__":
    demo.launch()
