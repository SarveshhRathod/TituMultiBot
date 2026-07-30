import aiohttp
import asyncio
import json
import base64
from core.crypto import CryptoEngine

def clean_str(val: str) -> str:
    if not val: 
        return ""
    return str(val).replace('\r', '').replace('\n', '').strip()

def extract_userid_from_token(token: str) -> str:
    try:
        parts = clean_str(token).split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (-len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
            
            uid = (
                decoded.get("user_id") or 
                decoded.get("id") or 
                decoded.get("userid") or 
                decoded.get("sub")
            )
            if not uid and isinstance(decoded.get("data"), dict):
                uid = (
                    decoded["data"].get("user_id") or 
                    decoded["data"].get("id") or 
                    decoded["data"].get("userid") or
                    decoded["data"].get("_id")
                )
            if uid:
                return str(uid)
    except Exception:
        pass
    return ""

async def get_appx_profile_userid(session, api_base: str, headers: dict) -> str:
    profile_urls = [
        f"{api_base}/get/get_user_profile",
        f"{api_base}/get/user_profile",
        f"{api_base}/get/myprofile"
    ]
    for url in profile_urls:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    data = res.get("data", {})
                    if isinstance(data, dict):
                        uid = data.get("userid") or data.get("id") or data.get("user_id")
                        if uid:
                            return str(uid)
        except Exception:
            pass
    return ""

class EdTechExtractor:
    
    @staticmethod
    async def appx_login(api_domain: str, email: str, password: str) -> tuple:
        api_domain = clean_str(api_domain).replace("https://", "").replace("http://", "").strip("/")
        api_base = f"https://{api_domain}"
        url = f"{api_base}/post/userLogin"
        
        headers = {
            "Auth-Key": "appxapi",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.9.1"
        }
        payload = {"email": clean_str(email), "password": clean_str(password)}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload, headers=headers) as resp:
                data = await resp.json()
                if data.get("status") == 1 or "data" in data:
                    token = clean_str(data["data"]["token"])
                    user_id = clean_str(data["data"]["userid"])
                    return token, user_id
                raise Exception(data.get("message", "Login Failed - Check Credentials"))

    @staticmethod
    async def fetch_appx_courses(api_domain: str, token: str, user_id: str = "") -> dict:
        api_domain = clean_str(api_domain).replace("https://", "").replace("http://", "").strip("/")
        api_base = f"https://{api_domain}"
        token = clean_str(token)
        user_id = clean_str(user_id) or extract_userid_from_token(token)

        headers = {
            "Client-Service": "Appx",
            "source": "website",
            "Auth-Key": "appxapi",
            "Authorization": token,
            "User-ID": user_id
        }
        
        async with aiohttp.ClientSession() as session:
            if not user_id:
                user_id = await get_appx_profile_userid(session, api_base, headers)
                headers["User-ID"] = user_id

            endpoints = [
                f"{api_base}/get/get_all_purchases?userid={user_id}&item_type=10",
                f"{api_base}/get/mycourseweb?userid={user_id}",
                f"{api_base}/get/mycourse?userid={user_id}",
                f"{api_base}/get/get_all_purchases?item_type=10",
                f"{api_base}/get/mycourseweb"
            ]

            for url in endpoints:
                try:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            res = await resp.json()
                            if res.get("data"):
                                return res
                except Exception:
                    pass

            return {}

    @staticmethod
    async def extract_appx_course(api_domain: str, token: str, user_id: str, course_id: str, file_path: str):
        api_domain = clean_str(api_domain).replace("https://", "").replace("http://", "").strip("/")
        api_base = f"https://{api_domain}"
        token = clean_str(token)
        user_id = clean_str(user_id) or extract_userid_from_token(token)

        headers = {
            "Client-Service": "Appx",
            "source": "website",
            "Auth-Key": "appxapi",
            "Authorization": token,
            "User-ID": user_id
        }
        
        lines = []

        async with aiohttp.ClientSession() as session:
            if not user_id:
                user_id = await get_appx_profile_userid(session, api_base, headers)
                headers["User-ID"] = user_id

            async def parse_video_item(item_id, item_title="Untitled", is_folder_wise=0):
                try:
                    url = f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&video_id={item_id}&ytflag=0&folder_wise_course={is_folder_wise}"
                    async with session.get(url, headers=headers) as resp:
                        res = await resp.json()
                        vd = res.get("data", {})
                        if not isinstance(vd, dict): return
                        
                        v_title = vd.get("Title") or item_title
                        link = vd.get("download_link") or vd.get("file_link") or ""
                        
                        if link:
                            dec_link = CryptoEngine.decrypt_appx(link)
                            if dec_link: lines.append(f"{v_title}: {dec_link}")
                        
                        enc_links = vd.get("encrypted_links", []) or vd.get("download_links", [])
                        if not link and enc_links:
                            for enc in enc_links:
                                path = enc.get("path") or enc.get("link")
                                if path:
                                    dec_path = CryptoEngine.decrypt_appx(path)
                                    if dec_path:
                                        lines.append(f"{v_title}: {dec_path}")
                                        break
                                        
                        for p_key in ["pdf_link", "pdf_link2", "material_link"]:
                            p_val = vd.get(p_key)
                            if p_val:
                                dec_pdf = CryptoEngine.decrypt_appx(p_val)
                                if dec_pdf: lines.append(f"{v_title} (PDF): {dec_pdf}")
                except Exception:
                    pass

            # --- STRATEGY 1: Appx V2 Folder Structure ---
            async def process_v2_folder(parent_id="-1"):
                try:
                    async with session.get(f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id={parent_id}", headers=headers) as f_resp:
                        res = await f_resp.json()
                        items = res.get("data", [])
                        if isinstance(items, list):
                            for item in items:
                                mt = item.get("material_type")
                                item_id = item.get("id")
                                item_title = item.get("Title") or item.get("title", "Untitled")
                                if mt == "FOLDER":
                                    await process_v2_folder(item_id)
                                else:
                                    await parse_video_item(item_id, item_title, is_folder_wise=1)
                except Exception:
                    pass

            await process_v2_folder("-1")

            # --- STRATEGY 2: Appx V3 Live Classes ---
            if not lines:
                try:
                    async with session.get(f"{api_base}/get/allsubjectfrmlivecourseclass?courseid={course_id}&start=-1", headers=headers) as s_resp:
                        s_data = await s_resp.json()
                        subjects = s_data.get("data", []) if isinstance(s_data.get("data"), list) else []

                    for subj in subjects:
                        subj_id = subj.get("subjectid")
                        if not subj_id: continue

                        async with session.get(f"{api_base}/get/alltopicfrmlivecourseclass?courseid={course_id}&subjectid={subj_id}&start=-1", headers=headers) as t_resp:
                            t_data = await t_resp.json()
                            topics = t_data.get("data", []) if isinstance(t_data.get("data"), list) else []

                        for topic in topics:
                            topic_id = topic.get("topicid")
                            if not topic_id: continue

                            for cid in ["1", "2", "", "0"]:
                                async with session.get(f"{api_base}/get/livecourseclassbycoursesubtopconceptapiv3?courseid={course_id}&subjectid={subj_id}&topicid={topic_id}&conceptid={cid}&start=-1", headers=headers) as c_resp:
                                    c_data = await c_resp.json()
                                    classes = c_data.get("data", []) if isinstance(c_data.get("data"), list) else []
                                    
                                    for item in classes:
                                        v_id = item.get("id")
                                        v_title = item.get("Title") or item.get("title", "Untitled")
                                        if v_id:
                                            await parse_video_item(v_id, v_title, is_folder_wise=0)
                except Exception:
                    pass

        unique_lines = []
        seen = set()
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        if not unique_lines:
            raise Exception("No video or PDF links found in this Course ID!")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(unique_lines))
