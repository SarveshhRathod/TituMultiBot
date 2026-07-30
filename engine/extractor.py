import aiohttp
import asyncio
import json
from core.crypto import CryptoEngine

class EdTechExtractor:
    
    @staticmethod
    async def fetch_appx_courses(api_domain: str, token: str, user_id: str = "") -> dict:
        """Fetch all purchased courses from an Appx platform."""
        api_base = f"https://{api_domain}" if not api_domain.startswith("http") else api_domain
        headers = {
            "Client-Service": "Appx",
            "Auth-Key": "appxapi",
            "Authorization": token,
            "User-ID": str(user_id)
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_base}/get/get_all_purchases?userid={user_id}&item_type=10", headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}

    @staticmethod
    async def appx_login(api_domain: str, email: str, password: str) -> tuple:
        """Authenticate user with Appx endpoint and return token & user_id."""
        api_base = f"https://{api_domain}" if not api_domain.startswith("http") else api_domain
        url = f"{api_base}/post/userLogin"
        headers = {
            "Auth-Key": "appxapi",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.9.1"
        }
        payload = {"email": email, "password": password}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload, headers=headers) as resp:
                data = await resp.json()
                if data.get("status") == 1 or "data" in data:
                    return data["data"]["token"], str(data["data"]["userid"])
                raise Exception(data.get("message", "Login Failed - Check ID/Password"))

    @staticmethod
    async def extract_appx_course(api_domain: str, token: str, user_id: str, course_id: str, file_path: str):
        """Recursively extract folder/video/PDF content and save to TXT file."""
        api_base = f"https://{api_domain}" if not api_domain.startswith("http") else api_domain
        headers = {
            "Client-Service": "Appx",
            "Auth-Key": "appxapi",
            "Authorization": token,
            "User-ID": str(user_id)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id=-1", headers=headers) as resp:
                res = await resp.json()
                
            items = res.get("data", [])
            lines = []

            async def process_item(item):
                mt = item.get("material_type")
                title = item.get("Title", "Untitled")
                item_id = item.get("id")
                
                if mt == "FOLDER":
                    async with session.get(f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id={item_id}", headers=headers) as f_resp:
                        sub_data = await f_resp.json()
                        for sub_item in sub_data.get("data", []):
                            await process_item(sub_item)
                else:
                    async with session.get(f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&folder_wise_course=1&ytflag=0&video_id={item_id}", headers=headers) as v_resp:
                        v_data = await v_resp.json()
                        vd = v_data.get("data", {})
                        v_title = vd.get("Title", title)
                        link = vd.get("download_link", "")
                        
                        if link:
                            dec_link = CryptoEngine.decrypt_appx(link)
                            lines.append(f"{v_title}: {dec_link}")
                        else:
                            for enc in vd.get("encrypted_links", []):
                                path = CryptoEngine.decrypt_appx(enc.get("path", ""))
                                if path:
                                    lines.append(f"{v_title}: {path}")
                                    break
                        if vd.get("pdf_link"):
                            lines.append(f"{v_title} (PDF): {CryptoEngine.decrypt_appx(vd['pdf_link'])}")

            await asyncio.gather(*(process_item(i) for i in items))

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))