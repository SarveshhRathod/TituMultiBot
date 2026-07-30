import asyncio
from aiohttp import web
from pyrogram import Client
from pyromod import listen
from config import API_ID, API_HASH, BOT_TOKEN, PORT
from plugins.handlers import register_handlers

# Initialize Pyrogram Client
app = Client(
    "TituMultiBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Register command handlers & callbacks
register_handlers(app)

# Health-Check HTTP Route for Hosting Platforms (Render/Koyeb/VPS)
async def handle_ping(request):
    return web.Response(text="TituMultiBot Engine is Active & Running Healthy.")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

async def main():
    await start_web_server()
    print("🌐 Health Check Web Server Started.")
    await app.start()
    print("🚀 TituMultiBot Started Successfully.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())