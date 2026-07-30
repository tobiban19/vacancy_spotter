import asyncio
import os
import sys
import threading
import gradio as gr
import uvicorn

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from api import app, repo
from bot_service import start_bot_polling
from fastapi.middleware.cors import CORSMiddleware

# Ensure CORS allows all origins
if not any(getattr(m, "cls", None) == CORSMiddleware for m in app.user_middleware):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def start_services_in_thread():
    async def run_services():
        bot, dp = await start_bot_polling()
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)

        server_task = asyncio.create_task(server.serve())
        polling_task = asyncio.create_task(dp.start_polling(bot))

        print("🚀 Vacancy Spotter SaaS Backend & Bot started in Gradio Space!")
        try:
            await asyncio.gather(server_task, polling_task)
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
