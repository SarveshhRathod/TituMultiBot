import os
import time
import asyncio
import cloudscraper
import aiofiles
import aiohttp
from pyrogram import Client
from pyrogram.types import Message
from config import COOKIES_FILE

# Global task cancel flags dictionary
CANCEL_FLAGS = {}

class BatchDownloader:

    @staticmethod
    async def download_file(url: str, output_path: str) -> bool:
        """Download raw files (e.g. PDFs/Images) via aiohttp."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(output_path, 'wb') as f:
                        await f.write(await response.read())
                    return True
        return False

    @staticmethod
    async def process_batch(client: Client, message: Message, links: list, quality: str, batch_name: str, credit: str, start_index: int = 1):
        """Unified processing loop for downloading TXT link batches with Cancel support."""
        chat_id = message.chat.id
        CANCEL_FLAGS[chat_id] = False
        
        total = len(links)
        status_msg = await message.reply_text(f"🚀 **Starting Engine...**\nTotal Links Found: `{total}`\n\n💡 Send `/cancel` anytime to stop!")

        for idx in range(start_index - 1, total):
            # Check if user requested cancellation
            if CANCEL_FLAGS.get(chat_id, False):
                CANCEL_FLAGS[chat_id] = False
                await status_msg.edit("🛑 **Batch Download Cancelled by User!**")
                return

            item = links[idx]
            if len(item) < 2:
                continue

            raw_title, raw_url = item[0].strip(), "https://" + item[1].strip()
            title = "".join(c for c in raw_title if c.isalnum() or c in (" ", "_", "-")).strip()
            count_str = str(idx + 1).zfill(3)
            file_name = f"{count_str}__{title[:40]}"

            caption = (
                f"📂 **Item ID:** `{count_str}`\n"
                f"📝 **Title:** `{title}`\n"
                f"📚 **Batch:** `{batch_name}`\n"
                f"⚡ **Extracted By:** {credit}"
            )

            try:
                # --- PDF / DOCUMENT HANDLING ---
                if ".pdf" in raw_url:
                    pdf_path = f"{file_name}.pdf"
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(raw_url)
                    if resp.status_code == 200:
                        with open(pdf_path, "wb") as f:
                            f.write(resp.content)
                        await client.send_document(message.chat.id, pdf_path, caption=caption)
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                    continue

                # --- VIDEO HANDLING (yt-dlp) ---
                out_template = f"{file_name}.%(ext)s"
                
                if "youtube" in raw_url or "youtu.be" in raw_url:
                    cmd = f'yt-dlp --cookies {COOKIES_FILE} -f "b[height<={quality}]/bv[height<={quality}]+ba/b" "{raw_url}" -o "{out_template}"'
                else:
                    cmd = f'yt-dlp -f "b[height<={quality}]/bv[height<={quality}]+ba/b" "{raw_url}" -o "{out_template}"'

                proc = await asyncio.create_subprocess_shell(cmd)
                await proc.communicate()

                # Find downloaded output file
                downloaded_file = None
                for ext in ["mp4", "mkv", "webm"]:
                    target = f"{file_name}.{ext}"
                    if os.path.exists(target):
                        downloaded_file = target
                        break

                if downloaded_file:
                    await client.send_video(message.chat.id, downloaded_file, caption=caption, supports_streaming=True)
                    if os.path.exists(downloaded_file):
                        os.remove(downloaded_file)
                else:
                    await client.send_message(message.chat.id, f"❌ **Failed to download:** {title}\n`{raw_url}`")

            except Exception as e:
                await client.send_message(message.chat.id, f"⚠️ **Error at {title}:** {str(e)}")

        await status_msg.edit("🎉 **Batch Processing Completed!**")
