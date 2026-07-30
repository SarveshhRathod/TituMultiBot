import aiohttp
import asyncio
import json
from core.crypto import CryptoEngine

def clean_str(val: str) -> str:
    if not val: 
        return ""
    return str(val).replace('\r', '').replace('\n', '').strip()

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
        headers = {
            "Client-Service": "Appx",
            "source": "website",
            "Auth-Key": "appxapi",
            "Authorization": clean_str(token),
            "User-ID": clean_str(user_id)
        }
        
        async with aiohttp.ClientSession() as session:
            # Method 1: Purchases Endpoint
            try:
                async with session.get(f"{api_base}/get/get_all_purchases?userid={user_id}&item_type=10", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("data"):
                            return data
            except Exception:
                pass

            # Method 2: Web Courses Fallback Endpoint
            try:
                async with session.get(f"{api_base}/get/mycourseweb?userid={user_id}", headers=headers) as resp2:
                    if resp2.status == 200:
                        return await resp2.json()
            except Exception:
                pass
                    
            return {}

    @staticmethod
    async def extract_appx_course(api_domain: str, token: str, user_id: str, course_id: str, file_path: str):
        api_domain = clean_str(api_domain).replace("https://", "").replace("http://", "").strip("/")
        api_base = f"https://{api_domain}"
        headers = {
            "Client-Service": "Appx",
            "source": "website",
            "Auth-Key": "appxapi",
            "Authorization": clean_str(token),
            "User-ID": clean_str(user_id)
        }
        
        lines = []

        async with aiohttp.ClientSession() as session:
            
            # --- ENGINE METHOD 1: Appx V2 Folder Structure ---
            async def process_v2_item(item):
                mt = item.get("material_type")
                title = item.get("Title") or item.get("title", "Untitled")
                item_id = item.get("id")
                
                if mt == "FOLDER":
                    try:
                        async with session.get(f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id={item_id}", headers=headers) as f_resp:
                            sub_data = await f_resp.json()
                            tasks = [process_v2_item(sub) for sub in sub_data.get("data", [])]
                            await asyncio.gather(*tasks)
                    except Exception:
                        pass
                else:
                    try:
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
                    except Exception:
                        pass

            try:
                async with session.get(f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id=-1", headers=headers) as resp:
                    v2_res = await resp.json()
                    if v2_res.get("data"):
                        tasks = [process_v2_item(item) for item in v2_res.get("data", [])]
                        await asyncio.gather(*tasks)
            except Exception:
                pass

            # --- ENGINE METHOD 2: Appx V3 Live Course Structure (Fallback) ---
            if not lines:
                try:
                    async with session.get(f"{api_base}/get/allsubjectfrmlivecourseclass?courseid={course_id}&start=-1", headers=headers) as s_resp:
                        subj_data = await s_resp.json()
                        subjects = subj_data.get("data", [])

                    for subj in subjects:
                        subj_id = subj.get("subjectid")
                        async with session.get(f"{api_base}/get/alltopicfrmlivecourseclass?courseid={course_id}&subjectid={subj_id}&start=-1", headers=headers) as t_resp:
                            topic_data = await t_resp.json()
                            topics = topic_data.get("data", [])

                        for topic in topics:
                            topic_id = topic.get("topicid")
                            async with session.get(f"{api_base}/get/livecourseclassbycoursesubtopconceptapiv3?courseid={course_id}&subjectid={subj_id}&topicid={topic_id}&conceptid=&start=-1", headers=headers) as c_resp:
                                class_data = await c_resp.json()
                                classes = class_data.get("data", [])

                            for item in classes:
                                v_id = item.get("id")
                                v_title = item.get("Title", "Untitled")
                                
                                async with session.get(f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&video_id={v_id}&ytflag=0&folder_wise_course=0", headers=headers) as vd_resp:
                                    v_info = await vd_resp.json()
                                    vd = v_info.get("data", {})
                                    title = vd.get("Title", v_title)
                                    vl = vd.get("download_link", "")
                                    
                                    if vl:
                                        lines.append(f"{title}: {CryptoEngine.decrypt_appx(vl)}")
                                    else:
                                        for enc in vd.get("encrypted_links", []):
                                            p = CryptoEngine.decrypt_appx(enc.get("path", ""))
                                            if p:
                                                lines.append(f"{title}: {p}")
                                                break
                                    if vd.get("pdf_link"):
                                        lines.append(f"{title} (PDF): {CryptoEngine.decrypt_appx(vd['pdf_link'])}")
                except Exception:
                    pass

        if not lines:
            raise Exception("No videos or PDFs found in this Course ID or access expired!")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
