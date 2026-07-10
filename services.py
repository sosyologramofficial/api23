"""
services.py - Yolly AI Service Provider
═══════════════════════════════════════
All AI service provider logic is contained here.
To switch providers, modify this file only.

Supported:
  - Video: Veo 3.1 Basic, Grok Imagine
  - Image: Nano Banana, Nano Banana Pro, Nano Banana 2, GPT-Image 2
"""

import random
import time
import requests
import string
import re
import base64
import json
import threading
import uuid
import queue as _queue
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

# ══════════════════════════════════════════════════════════════════════════════
# MODEL KONFİGÜRASYONLARI
# ══════════════════════════════════════════════════════════════════════════════

# Frontend model name → Yolly API model parameter
VIDEO_MODEL_MAP = {
    "VEO_3":        "veo3.1-basic",
    "SEEDANCE_2_0": "grok-imagine",
    "SORA_2":       "grok-imagine",
    "VIDU_Q3":      "grok-imagine",
    "QUALITY_V2_5": "veo3.1-basic",
}

IMAGE_MODEL_MAP = {
    "NANO_BANANA_PRO": "nano-banana-pro",
    "NANO_BANANA":     "nano-banana",
    "NANO_BANANA_2":   "nano-banana-2",
    "GPT_IMAGE_2":     "gpt-image-2",
}

# Yolly model capabilities & defaults
MODELS = {
    # ── Video ─────────────────────────────────────────────────────────────
    "veo3.1-basic": {
        "label": "Veo 3.1 Basic",
        "type": "video",
        "aspect_ratios": ["16:9", "9:16"],
        "resolutions": ["1080p"],
        "durations": ["5"],
        "supports_start_end_frame": True,
        "extra_params": {
            "negativePrompt": "",
            "audioUrl": "",
            "enablePromptExpansion": False,
            "cameraFixed": False,
            "generateAudio": False,
            "cfgScale": 0.5,
        },
    },
    "grok-imagine": {
        "label": "Grok Imagine",
        "type": "video",
        "aspect_ratios": ["16:9", "9:16", "1:1", "2:3", "3:2"],
        "resolutions": ["480p", "720p"],
        "durations": ["6", "10"],
        "supports_start_end_frame": False,
        "extra_params": {
            "negativePrompt": "",
            "audioUrl": "",
            "enablePromptExpansion": False,
            "cameraFixed": False,
            "cfgScale": 0.5,
        },
    },
    # ── Image ─────────────────────────────────────────────────────────────
    "nano-banana": {
        "label": "Nano Banana",
        "type": "image",
        "aspect_ratios": ["Auto", "1:1", "4:3", "3:4", "16:9", "9:16"],
        "resolutions": [],
    },
    "nano-banana-pro": {
        "label": "Nano Banana Pro",
        "type": "image",
        "aspect_ratios": ["1:1", "3:2", "2:3", "3:4", "4:3", "9:16", "16:9", "21:9"],
        "resolutions": ["1k", "2k", "4k"],
    },
    "nano-banana-2": {
        "label": "Nano Banana 2",
        "type": "image",
        "aspect_ratios": ["Auto", "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
        "resolutions": ["1k", "2k", "4k"],
    },
    "gpt-image-2": {
        "label": "GPT-Image 2",
        "type": "image",
        "aspect_ratios": ["Auto", "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
        "resolutions": ["1k", "2k", "4k"],
    },
}

# Frontend AR value → Yolly AR value (pass-through + Deevid legacy compat)
AR_MAP = {
    "16:9": "16:9", "9:16": "9:16", "1:1": "1:1",
    "3:4": "3:4", "4:3": "4:3", "3:2": "3:2", "2:3": "2:3",
    "4:5": "4:5", "5:4": "5:4", "21:9": "21:9",
    "Auto": "Auto", "AUTO": "Auto",
    # Deevid enum format compatibility
    "SIXTEEN_BY_NINE": "16:9", "NINE_BY_SIXTEEN": "9:16",
    "ONE_BY_ONE": "1:1", "THREE_BY_FOUR": "3:4",
    "FOUR_BY_THREE": "4:3", "THREE_BY_TWO": "3:2",
}

# Frontend resolution → Yolly resolution
RESOLUTION_MAP = {
    "1K": "1k", "2K": "2k", "4K": "4k",
    "1k": "1k", "2k": "2k", "4k": "4k",
    "480p": "480p", "720p": "720p", "1080p": "1080p",
}


def get_video_params(frontend_model):
    """Returns (yolly_model, resolution, duration, default_ar) for a frontend video model."""
    yolly_model = VIDEO_MODEL_MAP.get(frontend_model, "grok-imagine")
    cfg = MODELS.get(yolly_model, {})
    return (
        yolly_model,
        cfg.get("resolutions", ["720p"])[0],
        cfg.get("durations", ["6"])[0],
        cfg.get("aspect_ratios", ["16:9"])[0],
    )


# ══════════════════════════════════════════════════════════════════════════════
# SPAMOK EMAIL
# ══════════════════════════════════════════════════════════════════════════════

class eTemp:
    def random_email(self, length):
        return ''.join(
            random.SystemRandom().choice(string.ascii_lowercase + string.digits)
            for _ in range(length)
        )

    def getEmail(self):
        return self.random_email(15) + '@spamok.com'

    def getVerificationCode(self, mail, timeout=30):
        """Spamok üzerinden gelen 6 haneli doğrulama kodunu çeker."""
        address = mail.replace('@spamok.com', '')
        for _ in range(timeout):
            try:
                r = requests.get(f'https://api.spamok.com/v2/EmailBox/{address}', timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    for m in data.get('mails', []):
                        if 'Verification Code' in m.get('subject', '') or 'yolly.ai' in m.get('fromDomain', ''):
                            mail_id = m['id']
                            email_r = requests.get(f'https://api.spamok.com/v2/Email/{address}/{mail_id}', timeout=10)
                            if email_r.status_code == 200:
                                plain_text = email_r.json().get('messagePlain', '')
                                match = re.search(r'\b\d{6}\b', plain_text)
                                if match:
                                    return match.group(0)
            except Exception:
                pass
            time.sleep(2)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PROXY SİSTEMİ
# ══════════════════════════════════════════════════════════════════════════════

PROXYSCRAPE_URL = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get"
    "?request=display_proxies"
    "&proxy_format=protocolipport"
    "&format=text"
)


def fetch_proxies():
    """ProxyScrape'den proxy listesini çeker."""
    print("[*] Proxy listesi çekiliyor...")
    try:
        r = requests.get(PROXYSCRAPE_URL, timeout=10)
        proxies = [line.strip() for line in r.text.splitlines() if line.strip()]
        random.shuffle(proxies)
        print(f"[*] {len(proxies)} proxy bulundu.")
        return proxies
    except Exception as e:
        print(f"[-] Proxy listesi çekilemedi: {e}")
        return []


def test_proxy(proxy_url, test_url="https://www.yolly.ai", timeout=5):
    """Proxy'nin Yolly'ye ulaşabildiğini test eder."""
    try:
        r = requests.get(test_url, proxies={"http": proxy_url, "https": proxy_url}, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def find_working_proxy(max_workers=30):
    """Tüm proxy listesini paralel tarar, ilk çalışanı döndürür."""
    proxy_list = fetch_proxies()
    if not proxy_list:
        return None

    result_q = _queue.Queue()
    found_event = threading.Event()
    counter_lock = threading.Lock()
    tested_count = [0]
    total = len(proxy_list)

    def probe(proxy):
        if found_event.is_set():
            return
        ok = test_proxy(proxy)
        with counter_lock:
            tested_count[0] += 1
            idx = tested_count[0]
            last = idx == total
        if ok and not found_event.is_set():
            found_event.set()
            result_q.put(proxy)
            print(f"  [+] Çalışan proxy bulundu [{idx}/{total}]: {proxy}")
        elif last:
            result_q.put(None)

    print(f"[*] Paralel tarama başlıyor ({max_workers} thread)...")
    executor = ThreadPoolExecutor(max_workers=max_workers)
    executor.map(probe, proxy_list)
    working = result_q.get()
    found_event.set()
    executor.shutdown(wait=False, cancel_futures=True)

    if working:
        return working
    print("[-] Çalışan proxy bulunamadı.")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# YOLLY SESSION & LOGIN
# ══════════════════════════════════════════════════════════════════════════════

def make_yolly_session():
    """Creates a clean Yolly session with default headers."""
    s = requests.Session()
    s.headers.update({
        "accept": "application/json, text/plain, */*",
        "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "origin": "https://www.yolly.ai",
        "referer": "https://www.yolly.ai/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
    })
    return s


def serialize_session_data(session, extra=None):
    """Serialize session cookies + extra metadata (e.g. provider) for DB storage."""
    data = {"cookies": requests.utils.dict_from_cookiejar(session.cookies)}
    if extra:
        data.update(extra)
    return json.dumps(data)


def deserialize_session_data(json_str):
    """Restore session and metadata from stored JSON.
    Returns (session, data_dict).
    """
    data = json.loads(json_str)
    session = make_yolly_session()
    for name, value in data.get("cookies", {}).items():
        session.cookies.set(name, value, domain=".yolly.ai")
    return session, data


def login_yolly(email, password=None):
    """Login to Yolly AI using email verification code.
    Password parameter is ignored (Yolly uses email-only verification).
    Proxy is used ONLY for the send-code step.

    Returns (session, email) on success, (None, None) on failure.
    """
    session = make_yolly_session()

    # 1) Find proxy for send-code
    print(f"[*] Login başlatılıyor: {email}")
    working_proxy = find_working_proxy(max_workers=30)
    send_code_proxies = None
    if working_proxy:
        print(f"[*] Send-code proxy'si hazır: {working_proxy}")
        send_code_proxies = {"http": working_proxy, "https": working_proxy}
    else:
        print("[-] Proxy bulunamadı, send-code proxysiz gidecek.")

    # 2) send-code — WITH PROXY
    try:
        res = session.post(
            "https://www.yolly.ai/api/auth/send-code",
            json={"email": email},
            proxies=send_code_proxies,
            timeout=15,
        )
        if res.status_code != 200:
            print(f"[-] Send code başarısız ({email}): Status {res.status_code}")
            return None, None
    except Exception as e:
        print(f"[-] Send code hatası ({email}): {e}")
        return None, None

    # 3) Wait and check Spamok — retry up to 3 times with 15s waits
    temp = eTemp()
    code = None
    for attempt in range(1, 4):
        print(f"[*] {attempt}. deneme: 15 saniye bekleniyor (eski kodlar temizlensin)...")
        time.sleep(15)
        print(f"[*] Spamok kutusu kontrol ediliyor ({email})...")
        code = temp.getVerificationCode(email, timeout=15)
        if code:
            print(f"[+] Doğrulama kodu bulundu: {code}")
            break
        if attempt < 3:
            print(f"[-] Kod bulunamadı, tekrar deneniyor...")
        else:
            print(f"[-] Doğrulama kodu 3 denemede de alınamadı ({email})")
            return None, None

    # 4) CSRF — no proxy
    try:
        csrf_res = session.get("https://www.yolly.ai/api/auth/csrf", timeout=15)
        if csrf_res.status_code != 200:
            print(f"[-] CSRF token alınamadı ({email})")
            return None, None
        csrf_token = csrf_res.json().get("csrfToken")
    except Exception as e:
        print(f"[-] CSRF hatası ({email}): {e}")
        return None, None

    # 5) Verify — NO PROXY
    verify_payload = {
        "email": email,
        "code": code,
        "firstVisitPage": "/",
        "redirect": "false",
        "callbackUrl": "https://www.yolly.ai/",
        "csrfToken": csrf_token,
    }
    verify_headers = dict(session.headers)
    verify_headers["content-type"] = "application/x-www-form-urlencoded"

    try:
        res = session.post(
            "https://www.yolly.ai/api/auth/callback/verification-code?",
            data=verify_payload,
            headers=verify_headers,
            timeout=15,
        )
        if res.status_code != 200:
            print(f"[-] Doğrulama başarısız ({email}): Status {res.status_code}")
            return None, None
    except Exception as e:
        print(f"[-] Verify hatası ({email}): {e}")
        return None, None

    print(f"[+] Login başarılı: {email}")
    return session, email


def check_credits(session):
    """Check remaining credits for a logged-in session. Returns int."""
    try:
        res = session.get("https://www.yolly.ai/api/user/credits", timeout=15)
        if res.status_code == 200:
            return int(res.json().get("left_credits", 0))
    except Exception:
        pass
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_image(session, image_bytes, mime_type="image/png"):
    """Upload image bytes to Yolly. Returns URL string or None."""
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    base64_string = f"data:{mime_type};base64,{b64_data}"
    timestamp = int(time.time() * 1000)
    file_name = f"upload-{timestamp}-0.png"

    payload = {"base64Data": base64_string, "fileName": file_name}

    try:
        res = session.post(
            "https://www.yolly.ai/api/kie/upload", json=payload, timeout=60
        )
        if res.status_code == 200:
            url = res.json().get("data", {}).get("url")
            if url:
                print(f"[+] Resim yüklendi: {url[:80]}...")
                return url
        print(f"[-] Resim yükleme başarısız: {res.text[:200]}")
    except Exception as e:
        print(f"[-] Resim yükleme hatası: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def create_video(session, prompt, yolly_model, input_mode, images,
                 resolution, duration, aspect_ratio):
    """Submit video generation to Yolly.
    images: list of uploaded image URLs.
    Returns (task_id, provider) or ("INSUFFICIENT_CREDITS", None) or (None, None).
    """
    model_config = MODELS.get(yolly_model, {})

    payload = {
        "model": yolly_model,
        "prompt": prompt,
        "images": images or [],
        "inputMode": input_mode,
        "isPublic": True,
        "resolution": resolution,
        "duration": duration,
        "aspectRatio": aspect_ratio,
        "locale": "en",
    }

    extra = model_config.get("extra_params", {
        "negativePrompt": "", "audioUrl": "",
        "enablePromptExpansion": False, "cameraFixed": False, "cfgScale": 0.5,
    })
    payload.update(extra)

    session.headers.update({"referer": "https://www.yolly.ai/video"})

    try:
        res = session.post(
            "https://www.yolly.ai/api/video/create", json=payload, timeout=20
        )
        if "Insufficient credits" in res.text:
            return "INSUFFICIENT_CREDITS", None
        if res.status_code != 200:
            print(f"[-] Video create başarısız: {res.text[:300]}")
            return None, None
        data = res.json()
        task_id = data.get("id")
        provider = data.get("provider", yolly_model)
        if not task_id:
            print(f"[-] Task ID alınamadı: {data}")
            return None, None
        return task_id, provider
    except Exception as e:
        print(f"[-] Video create hatası: {e}")
        return None, None


def poll_video(session, task_id, provider, shutdown_event=None,
               max_polls=600, interval=3):
    """Poll Yolly for video completion.
    Returns (status_str, video_url).
    status_str: 'completed' | 'failed' | 'timeout' | 'shutdown'
    """
    params = {"id": task_id, "provider": provider}

    for _ in range(max_polls):
        if shutdown_event and shutdown_event.wait(interval):
            return "shutdown", None
        elif not shutdown_event:
            time.sleep(interval)

        try:
            res = session.get(
                "https://www.yolly.ai/api/video/query", params=params, timeout=15
            )
            if res.status_code != 200:
                continue

            q = res.json()
            # Flat format (Veo 3.1): {status, video_url, ...}
            # Nested format (grok):  {data: {status, videoUrl, ...}}
            nested = q.get("data") if isinstance(q.get("data"), dict) else None

            if nested:
                status = nested.get("status")
                video_url = nested.get("videoUrl")
            else:
                status = q.get("status")
                video_url = (
                    q.get("video_url")
                    or q.get("r2_video_url")
                    or (q.get("video_urls") or [None])[0]
                )

            if status == "completed" and video_url:
                return "completed", video_url
            if status in ("failed", "error"):
                return "failed", None
        except Exception as e:
            print(f"  [!] Video poll hatası: {e}")

    return "timeout", None


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def create_image(session, prompt, yolly_model, aspect_ratio, resolution=None,
                 reference_images=None, number_of_images=1):
    """Submit image generation to Yolly.
    reference_images: list of uploaded image URLs (not base64).
    Returns task_id string, or "INSUFFICIENT_CREDITS", or None.
    """
    model_config = MODELS.get(yolly_model, {})
    active_tab = "image" if reference_images else "text"

    payload = {
        "model": yolly_model,
        "prompt": prompt,
        "referenceImages": reference_images or [],
        "aspectRatio": aspect_ratio,
        "numberOfImages": number_of_images,
        "activeTab": active_tab,
        "isPublic": True,
        "locale": "en",
    }

    # Only add resolution for models that support it
    if resolution and model_config.get("resolutions"):
        payload["resolution"] = resolution

    session.headers.update({"referer": "https://www.yolly.ai/ai-image-generator"})

    try:
        res = session.post(
            "https://www.yolly.ai/api/image/create", json=payload, timeout=20
        )
        if "Insufficient credits" in res.text:
            return "INSUFFICIENT_CREDITS"
        if res.status_code != 200:
            print(f"[-] Image create başarısız: {res.text[:300]}")
            return None
        task_id = res.json().get("id")
        if not task_id:
            print(f"[-] Image task ID alınamadı")
            return None
        return task_id
    except Exception as e:
        print(f"[-] Image create hatası: {e}")
        return None


def poll_image(session, task_id, shutdown_event=None,
               max_polls=600, interval=2):
    """Poll Yolly for image completion.
    Returns (status_str, image_url_list).
    status_str: 'completed' | 'failed' | 'timeout' | 'shutdown'
    """
    for _ in range(max_polls):
        if shutdown_event and shutdown_event.wait(interval):
            return "shutdown", None
        elif not shutdown_event:
            time.sleep(interval)

        try:
            res = session.get(
                "https://www.yolly.ai/api/image/query",
                params={"id": task_id},
                timeout=15,
            )
            if res.status_code != 200:
                continue

            q = res.json()
            status = q.get("status")

            if status == "completed":
                urls = q.get("image_urls", []) or q.get("result", {}).get("imageUrls", [])
                return "completed", urls
            if status in ("failed", "error"):
                return "failed", None
        except Exception as e:
            print(f"  [!] Image poll hatası: {e}")

    return "timeout", None


# ══════════════════════════════════════════════════════════════════════════════
# MORPH STUDIO AI (NANO BANANA 2) INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

BASE_HEADERS_MORPH = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://app.morphstudio.com",
    "priority": "u=1, i",
    "referer": "https://app.morphstudio.com/",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}


class eTemp:
    def random_email(self, length):
        return ''.join(
            random.SystemRandom().choice(string.ascii_lowercase + string.digits)
            for _ in range(length)
        )

    def getEmail(self):
        return self.random_email(15) + '@spamok.com'

    def getVerifyLink(self, mail, shutdown_event=None):
        username = mail.replace('@spamok.com', '')
        print(f"[SpamOK] Mail bekleniyor: {mail}")

        for attempt in range(30):
            if shutdown_event and shutdown_event.is_set():
                return None
            try:
                r = requests.get(f'https://api.spamok.com/v2/EmailBox/{username}', timeout=10)
                if r.status_code == 200:
                    mails = r.json().get('mails', [])

                    for m in mails:
                        subject = m.get('subject', '')
                        if 'Verify' in subject or 'Confirm' in subject:
                            mail_id = m['id']
                            print(f"[SpamOK] Mail bulundu (id: {mail_id}), icerik cekiliyor...")

                            detail = requests.get(f'https://api.spamok.com/v2/Email/{username}/{mail_id}', timeout=10)
                            if detail.status_code == 200:
                                html = detail.json().get('messageHtml', '')

                                soup = BeautifulSoup(html, 'html.parser')
                                for a in soup.find_all('a', href=True):
                                    href = a['href']
                                    if 'morphstudio.com/redirect-verify-email' in href:
                                        return href

                                match = re.search(
                                    r'(https://app\.morphstudio\.com/redirect-verify-email[^\s\'"<>]+)',
                                    html
                                )
                                if match:
                                    return match.group(1).strip()
            except Exception as e:
                print(f"[SpamOK] Hata: {e}")

            time.sleep(1)

        return None


def register_morph(shutdown_event=None):
    """Registers a new account on Morph Studio and returns the authenticated session, email, and password."""
    session = requests.Session()
    temp = eTemp()
    email = temp.getEmail()
    password = "gAAAAABpxPNrzSpgynpZv_bnHzlIf--xIbpSHDNVbLKG6nsox_eUgWjgfoyXdTPe6gPw2ELclPktqE59ViIQB8WR2AoT2wUh2Q=="
    
    try:
        register_resp = session.post(
            "https://api.morphstudio.com/api/user/register",
            headers=BASE_HEADERS_MORPH,
            json={"email": email, "password": password},
            timeout=15
        )
        if register_resp.status_code != 200:
            print(f"[-] Morph register failed: {register_resp.text}")
            return None, None, None
            
        user_id = register_resp.json().get("userId")
        if not user_id:
            return None, None, None
            
        verify_resp = session.post(
            "https://api.morphstudio.com/api/user/send-verify-email",
            headers=BASE_HEADERS_MORPH,
            json={"userId": user_id},
            timeout=15
        )
        
        verify_link = temp.getVerifyLink(email, shutdown_event)
        if not verify_link:
            return None, None, None
            
        parsed = urlparse(verify_link)
        params = parse_qs(parsed.query)
        
        verify_email_payload = {
            "email":  unquote(params["email"][0]),
            "token":  params["token"][0],
            "userId": params["userId"][0],
        }
        
        verify_email_resp = session.post(
            "https://api.morphstudio.com/api/user/verify-email",
            headers=BASE_HEADERS_MORPH,
            json=verify_email_payload,
            timeout=15
        )
        if verify_email_resp.status_code != 200:
            print(f"[-] Morph verify-email failed: {verify_email_resp.text}")
            return None, None, None
            
        return session, email, password
    except Exception as e:
        print(f"[-] Morph registration error: {e}")
        return None, None, None


def upload_image_morph(session, image_bytes):
    """Uploads image bytes to Morph Studio GCS."""
    try:
        filename = f"{uuid.uuid4().hex}.jpg"
        
        create_resp = session.post(
            "https://api.morphstudio.com/api/v1/storage/create",
            headers=BASE_HEADERS_MORPH,
            json={"displayName": filename, "isPublic": True},
            timeout=15
        )
        if create_resp.status_code != 200:
            print(f"[-] Morph storage create failed: {create_resp.text}")
            return None
            
        create_data = create_resp.json()
        object_id  = create_data["objectId"]
        presigned  = create_data["presigned"]
        upload_url = presigned["url"]
        fields     = presigned["fields"]
        
        form_fields = [
            ("key",            fields["key"]),
            ("AWSAccessKeyId", fields["AWSAccessKeyId"]),
            ("policy",         fields["policy"]),
            ("signature",      fields["signature"]),
            ("file",           (filename, image_bytes, "image/jpeg")),
        ]
        
        gcs_headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "origin": "https://app.morphstudio.com",
            "referer": "https://app.morphstudio.com/",
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        }
        
        upload_resp = requests.post(upload_url, headers=gcs_headers, files=form_fields, timeout=20)
        if upload_resp.status_code not in (200, 204):
            print(f"[-] Morph GCS upload failed: {upload_resp.text}")
            return None
            
        return {"objectId": object_id, "key": fields.get("key")}
    except Exception as e:
        print(f"[-] Morph upload image error: {e}")
        return None


def create_image_morph(session, prompt, aspect_ratio, resolution=None, input_images=None):
    """Submits the image generation task to Morph Studio."""
    params = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "number_of_images": 1,
        "quality": resolution or "4k",
    }
    
    if input_images:
        for idx, img in enumerate(input_images, start=1):
            obj_id = img["objectId"]
            key = img["key"]
            params[f"input_image{idx}"] = obj_id
            params[f"input_image{idx}_url"] = f"https://morph-app-cmr-prod.morphstudio.com/{key}"

    payload = {
        "session_id": "",
        "model_id": "google/nano-banana-2",
        "sessionType": "video",
        "params": params
    }

    try:
        resp = session.post(
            "https://api.morphstudio.com/api/v1/moca/media_session/video/node/create",
            headers=BASE_HEADERS_MORPH,
            json=payload,
            timeout=20
        )
        if resp.status_code != 200:
            print(f"[-] Morph create image node failed: {resp.text}")
            return None
        node_id = resp.json().get("nodeId")
        return node_id
    except Exception as e:
        print(f"[-] Morph create image error: {e}")
        return None


def poll_image_morph(session, node_id, shutdown_event=None, max_polls=300, interval=5):
    """Polls Morph Studio for image completion."""
    for _ in range(max_polls):
        if shutdown_event and shutdown_event.is_set():
            return "shutdown", None
        
        try:
            list_resp = session.get(
                "https://api.morphstudio.com/api/v1/moca/media_session/video/list?limit=100",
                headers=BASE_HEADERS_MORPH,
                timeout=15
            )
            if list_resp.status_code != 200:
                time.sleep(interval)
                continue
            data = list_resp.json()
            
            for date, sessions_list in data.get("sessions", {}).items():
                for s in sessions_list:
                    for node in s.get("recentNodes", []):
                        if node.get("external_id") == node_id:
                            status = node.get("status", "")
                            
                            if status == "failed":
                                print(f"[-] Morph image creation failed: {node.get('error_message', '')}")
                                return "failed", None
                                
                            urls = []
                            if node.get("cdn_url"):
                                urls.append(node["cdn_url"])
                            for f in node.get("files", []):
                                if isinstance(f, dict) and f.get("url"):
                                    urls.append(f["url"])
                                elif isinstance(f, str):
                                    urls.append(f)
                            for img in node.get("images", []):
                                if isinstance(img, dict) and img.get("url"):
                                    urls.append(img["url"])
                                elif isinstance(img, str):
                                    urls.append(img)
                                    
                            multi = node.get("multi_outputs")
                            if isinstance(multi, list):
                                for m in multi:
                                    if isinstance(m, str):
                                        urls.append(m)
                                    elif isinstance(m, dict):
                                        if m.get("url"):
                                            urls.append(m["url"])
                                        elif m.get("cdn_url"):
                                            urls.append(m["cdn_url"])
                                            
                            seen = set()
                            urls = [x for x in urls if not (x in seen or seen.add(x))]
                            
                            if urls:
                                return "completed", urls
        except Exception as e:
            print(f"  [!] Morph poll error: {e}")
            
        time.sleep(interval)
            
    return "timeout", None
