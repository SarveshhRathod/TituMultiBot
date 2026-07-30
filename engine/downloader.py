import os
import re
import time
import asyncio
import cloudscraper
import aiofiles
import aiohttp
from pyrogram import Client
from pyrogram.types import Message
from config import COOKIES_FILE

CANCEL_FLAGS = {}

class BatchDownloader:

    @staticmethod
    def parse_txt_line(line: str):
        """Cleanly parse Title and URL from TXT file lines without duplicating https://."""
        line = line.strip()
        if not line:
            return None, None
            
        url = None
        title = "Untitled"
        
        if "https://" in line:
            parts = line.split("https://", 1)
            title = parts[0].strip().rstrip(":").rstrip("-").strip()
            url = "https://" + parts[1].strip()
        elif "http://" in line:
            parts = line.split("http://", 1)
            title = parts[0].strip().rstrip(":").rstrip("-").strip()
            url = "http://" + parts[1].strip()
            
        if not url:
            return None, None
            
        if not title:
            title = "Media_File"
            
        return title, url

    @staticmethod
    async def process_batch(client: Client, message: Message, content_lines: list, quality: str, batch_name: str, credit: str, start_index: int = 1):
        chat_id = message.chat.id
        CANCEL_FLAGS[chat_id] = False
        
        # Parse all lines cleanly
        valid_items = []
        for line in content_lines:
            t, u = BatchDownloader.parse_txt_line(line)
            if t and u:
                valid_items.append((t, u))

        total = len(valid_items)
        if total == 0:
            return await message.reply_text("❌ No valid video or PDF URLs found in the file!")

        status_msg = await message.reply_text(
            f"🚀 **Starting Enterprise Downloader Engine...**\n"
            f"📊 Total Items: `{total}`\n"
            f"🎬 Quality: `{quality}p`\n\n"
            f"💡 Send `/cancel` anytime to stop!"
        )

        for idx in range(start_index - 1, total):
            if CANCEL_FLAGS.get(chat_id, False):
                CANCEL_FLAGS[chat_id] = False
                await status_msg.edit("🛑 **Batch Download Cancelled by User!**")
                return

            title, raw_url = valid_items[idx]
            clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
            count_str = str(idx + 1).zfill(3)
            file_name = f"{count_str}__{clean_title[:35]}"

            caption = (
                f"📂 **Item ID:** `{count_str}`\n"
                f"📝 **Title:** `{clean_title}`\n"
                f"📚 **Batch:** `{batch_name}`\n"
                f"⚡ **Extracted By:** {credit}"
            )

            try:
                # --- PDF / DOCUMENT HANDLING ---
                if ".pdf" in raw_url.lower():
                    pdf_path = f"{file_name}.pdf"
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(raw_url)
                    if resp.status_code == 200 and len(resp.content) > 100:
                        with open(pdf_path, "wb") as f:
                            f.write(resp.content)
                        await client.send_document(message.chat.id, pdf_path, caption=caption)
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                        continue

                # --- VIDEO HANDLING (yt-dlp Enterprise Flags) ---
                out_template = f"{file_name}.%(ext)s"
                
                ydl_opts = (
                    f'--no-check-certificates '
                    f'--user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" '
                    f'--add-header "Referer:https://classx.co.in/" '
                    f'--concurrent-fragments 5 '
                )

                if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 10:
                    ydl_opts += f'--cookies {COOKIES_FILE} '

                cmd = f'yt-dlp {ydl_opts} -f "b[height<={quality}]/bv[height<={quality}]+ba/b/best" "{raw_url}" -o "{out_template}"'

                proc = await asyncio.create_subprocess_shell(cmd)
                await proc.communicate()

                # Find downloaded video file
                downloaded_file = None
                for ext in ["mp4", "mkv", "webm", "ts"]:
                    target = f"{file_name}.{ext}"
                    if os.path.exists(target) and os.path.getsize(target) > 1000:
                        downloaded_file = target
                        break

                if downloaded_file:
                    await client.send_video(message.chat.id, downloaded_file, caption=caption, supports_streaming=True)
                    if os.path.exists(downloaded_file):
                        os.remove(downloaded_file)
                else:
                    await client.send_message(message.chat.id, f"❌ **Failed to download:** `{clean_title}`\n🔗 `{raw_url}`")

            except Exception as e:
                await client.send_message(message.chat.id, f"⚠️ **Error at {clean_title}:** {str(e)}")

        await status_msg.edit("🎉 **Batch Download Task Successfully Completed!**")
