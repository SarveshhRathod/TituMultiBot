import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import OWNER_ID
from core.db import db
from engine.extractor import EdTechExtractor
from engine.downloader import BatchDownloader, CANCEL_FLAGS

# Dynamic Start Menu Builder (Admin Panel button is visible ONLY to Admins/Sudo Users)
async def get_start_menu(user_id: int) -> InlineKeyboardMarkup:
    sudos = await db.get_sudo_users()
    buttons = [
        [InlineKeyboardButton("📦 Extract Courses", callback_data="mode_extract")],
        [InlineKeyboardButton("📥 Download TXT File", callback_data="mode_download")]
    ]
    if user_id in sudos:
        buttons.append([InlineKeyboardButton("⚙️ Admin Control Panel", callback_data="mode_admin")])
    return InlineKeyboardMarkup(buttons)

EXTRACT_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("Appx (V2/V3)", callback_data="ext_appx")],
    [InlineKeyboardButton("🔙 Back Home", callback_data="home")]
])

ADMIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 View Current Config", callback_data="adm_view")],
    [InlineKeyboardButton("📢 Set Log Channel", callback_data="adm_set_log"), InlineKeyboardButton("➕ Add Sudo User", callback_data="adm_add_sudo")],
    [InlineKeyboardButton("🍪 Upload YT Cookies", callback_data="adm_set_cookies"), InlineKeyboardButton("🚨 Toggle Maintenance", callback_data="adm_toggle_maint")],
    [InlineKeyboardButton("🔙 Back Home", callback_data="home")]
])

def sanitize_filename(name: str) -> str:
    """Remove slashes and special characters to prevent directory errors."""
    if not name: return "file"
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def register_handlers(app: Client):

    @app.on_message(filters.command("start"))
    async def start_cmd(client: Client, message: Message):
        user_id = message.from_user.id
        maint = await db.get_setting("maintenance", False)
        sudos = await db.get_sudo_users()
        
        if maint and user_id not in sudos:
            return await message.reply_text("🚨 **Bot is currently under Maintenance Mode! Please try again later.**")

        start_menu = await get_start_menu(user_id)
        await message.reply_text(
            f"👋 **Welcome {message.from_user.mention} to TituMultiBot!**\n\n"
            "An enterprise multi-purpose engine for course extraction & media batch downloader.",
            reply_markup=start_menu
        )

    # --- CANCEL COMMAND HANDLER ---
    @app.on_message(filters.command(["cancel", "stop"]))
    async def cancel_handler(client: Client, message: Message):
        chat_id = message.chat.id
        CANCEL_FLAGS[chat_id] = True
        await message.reply_text("🛑 **Cancellation requested! Stopping process...**")

    @app.on_message(filters.command("download") | filters.command("upload"))
    async def download_cmd(client: Client, message: Message):
        if not await db.is_premium(message.from_user.id):
            return await message.reply_text("❌ **You do not have access to use downloader!**")

        ask_file = await message.reply_text("📂 **Send your `.txt` file containing URLs:**\n(Send `/cancel` to stop)")
        response: Message = await client.listen(message.chat.id)
        
        if response.text and response.text.startswith("/"):
            return await message.reply_text("❌ **Operation Cancelled.**")

        if not response.document or not response.document.file_name.endswith(".txt"):
            return await message.reply_text("❌ **Invalid file! Please send a `.txt` document.**")

        txt_path = await response.download()
        
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read().splitlines()
        if os.path.exists(txt_path):
            os.remove(txt_path)

        links = [line.split("://", 1) for line in content if "://" in line]
        if not links:
            return await message.reply_text("❌ No valid URLs found in file.")

        await message.reply_text(f"🔗 **Found {len(links)} links!**\nSend Quality (e.g., `360`, `480`, `720`):")
        res_msg: Message = await client.listen(message.chat.id)
        
        if res_msg.text and res_msg.text.startswith("/"):
            return await message.reply_text("❌ **Operation Cancelled.**")
            
        quality = res_msg.text.strip() if res_msg.text and res_msg.text.strip().isdigit() else "480"

        await message.reply_text("🏷️ **Enter Batch Name:**")
        b_msg: Message = await client.listen(message.chat.id)
        
        if b_msg.text and b_msg.text.startswith("/"):
            return await message.reply_text("❌ **Operation Cancelled.**")
            
        batch_name = sanitize_filename(b_msg.text)

        await BatchDownloader.process_batch(
            client=client,
            message=message,
            links=links,
            quality=quality,
            batch_name=batch_name,
            credit=message.from_user.mention
        )

    # --- ROUTER FOR BUTTON CALLBACKS ---
    @app.on_callback_query()
    async def cb_router(client: Client, query: CallbackQuery):
        data = query.data
        user_id = query.from_user.id
        sudos = await db.get_sudo_users()

        if data == "home":
            start_menu = await get_start_menu(user_id)
            await query.message.edit_text("⚡ **Select an Option from Menu:**", reply_markup=start_menu)

        elif data == "mode_admin":
            if user_id not in sudos:
                return await query.answer("⛔ Admin Only Area!", show_alert=True)
            await query.message.edit_text("⚙️ **Welcome to Live Admin Control Panel:**", reply_markup=ADMIN_MENU)

        elif data == "adm_view":
            if user_id not in sudos: return
            log_ch = await db.get_setting("log_channel", "Not Configured")
            maint = await db.get_setting("maintenance", False)
            sudo_list = ", ".join([f"`{s}`" for s in sudos])
            
            info_text = (
                f"🛠️ **CURRENT BOT DYNAMIC CONFIGURATION:**\n\n"
                f"📢 **Log Channel ID:** `{log_ch}`\n"
                f"🚨 **Maintenance Mode:** `{maint}`\n"
                f"👑 **Owner ID:** `{OWNER_ID}`\n"
                f"👥 **Sudo Users:** {sudo_list}\n"
            )
            await query.message.edit_text(info_text, reply_markup=ADMIN_MENU)

        elif data == "adm_set_log":
            if user_id not in sudos: return
            await query.message.delete()
            ask = await client.send_message(query.message.chat.id, "📢 **Send Channel ID for Logs (e.g., `-100123456789`):**")
            res = await client.listen(query.message.chat.id)
            try:
                ch_id = int(res.text.strip())
                await db.set_setting("log_channel", ch_id)
                await client.send_message(query.message.chat.id, f"✅ **Log Channel Updated To:** `{ch_id}`")
            except Exception:
                await client.send_message(query.message.chat.id, "❌ Invalid Channel ID!")

        elif data == "adm_add_sudo":
            if user_id != OWNER_ID:
                return await query.answer("⛔ Only Owner can add Sudo Users!", show_alert=True)
            await query.message.delete()
            ask = await client.send_message(query.message.chat.id, "👥 **Send User ID to add as Sudo:**")
            res = await client.listen(query.message.chat.id)
            if res.text and res.text.isdigit():
                await db.add_sudo(int(res.text))
                await client.send_message(query.message.chat.id, f"✅ **User `{res.text}` added to Sudo Users!**")
            else:
                await client.send_message(query.message.chat.id, "❌ Invalid User ID!")

        elif data == "adm_set_cookies":
            if user_id not in sudos: return
            await query.message.delete()
            ask = await client.send_message(query.message.chat.id, "🍪 **Send `youtube_cookies.txt` file:**")
            res = await client.listen(query.message.chat.id)
            if res.document:
                await res.download(file_name="youtube_cookies.txt")
                await client.send_message(query.message.chat.id, "✅ **YouTube Cookies File Updated Successfully!**")
            else:
                await client.send_message(query.message.chat.id, "❌ Invalid file!")

        elif data == "adm_toggle_maint":
            if user_id not in sudos: return
            curr = await db.get_setting("maintenance", False)
            new_val = not curr
            await db.set_setting("maintenance", new_val)
            await query.answer(f"Maintenance Mode set to {new_val}", show_alert=True)
            await query.message.edit_text(f"🚨 **Maintenance Mode is now:** `{new_val}`", reply_markup=ADMIN_MENU)

        elif data == "mode_extract":
            await query.message.edit_text("🎯 **Choose Extraction Engine:**", reply_markup=EXTRACT_MENU)

        elif data == "ext_appx":
            await query.message.delete()
            ask_api = await client.send_message(query.message.chat.id, "🌐 **Send Appx API Domain (e.g., `tcsexamzoneapi.classx.co.in`):**")
            api_res = await client.listen(query.message.chat.id)
            
            if api_res.text and api_res.text.startswith("/"):
                return await client.send_message(query.message.chat.id, "❌ **Operation Cancelled.**")
                
            api_domain = api_res.text.strip()

            ask_auth = await client.send_message(query.message.chat.id, "🔑 **Send Credentials as `Email*Password` OR send `Token` directly:**")
            auth_res = await client.listen(query.message.chat.id)
            
            if auth_res.text and auth_res.text.startswith("/"):
                return await client.send_message(query.message.chat.id, "❌ **Operation Cancelled.**")
                
            auth_txt = auth_res.text.strip()

            try:
                if "*" in auth_txt:
                    email, pwd = auth_txt.split("*", 1)
                    token, user_id = await EdTechExtractor.appx_login(api_domain, email, pwd)
                else:
                    token = auth_txt
                    user_id = ""

                purchases = await EdTechExtractor.fetch_appx_courses(api_domain, token, user_id)
                course_list_str = "**Your Available Courses:**\n\n"
                
                has_courses = False
                data_items = purchases.get("data", [])
                if isinstance(data_items, dict):
                    data_items = data_items.get("courses") or data_items.get("data") or []

                if isinstance(data_items, list):
                    for item in data_items:
                        if isinstance(item, dict):
                            if "coursedt" in item and isinstance(item["coursedt"], list):
                                for ct in item["coursedt"]:
                                    ci = ct.get("id")
                                    cn = ct.get("course_name") or ct.get("title")
                                    if ci and cn:
                                        course_list_str += f"`{ci}` - **{cn}**\n"
                                        has_courses = True
                            else:
                                ci = item.get("id") or item.get("course_id")
                                cn = item.get("course_name") or item.get("title") or item.get("name")
                                if ci and cn:
                                    course_list_str += f"`{ci}` - **{cn}**\n"
                                    has_courses = True

                if not has_courses:
                    return await client.send_message(query.message.chat.id, "❌ No active courses found for this account!")

                await client.send_message(query.message.chat.id, course_list_str)
                await client.send_message(query.message.chat.id, "📌 **Send Course ID to extract:**")
                cid_res = await client.listen(query.message.chat.id)
                
                if cid_res.text and cid_res.text.startswith("/"):
                    return await client.send_message(query.message.chat.id, "❌ **Operation Cancelled.**")
                
                clean_cid = sanitize_filename(cid_res.text)
                out_file = f"Course_{clean_cid}.txt"
                
                status_msg = await client.send_message(query.message.chat.id, "⏳ **Extracting Course Content... Please wait.**")
                
                await EdTechExtractor.extract_appx_course(api_domain, token, user_id, clean_cid, out_file)
                
                if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                    await client.send_document(query.message.chat.id, out_file)
                    await status_msg.delete()
                    os.remove(out_file)
                else:
                    await status_msg.edit("❌ Failed to extract content or course is empty!")

            except Exception as e:
                await client.send_message(query.message.chat.id, f"❌ **Error:** {str(e)}")

        elif data == "mode_download":
            await query.message.edit_text("📥 Send `/download` command to start batch downloader workflow.")
