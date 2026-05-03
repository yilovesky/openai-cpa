import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from curl_cffi import requests
from utils import config as cfg


class TempMailOrgService:
    BASE_URL = "https://mail.chatgpt.org.uk"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"

    def __init__(self, proxies: Optional[Dict[str, str]] = None):
        self.proxies = proxies
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
        })
        self.session.verify = False
        if self.proxies:
            self.session.proxies.update(self.proxies)

    def _load_browser_auth(self, email: str = "") -> Optional[dict]:
        try:
            r = self.session.get(f"{self.BASE_URL}/", timeout=15)
            if r.status_code != 200:
                return None
            m = re.search(r"window\.__BROWSER_AUTH\s*=\s*(\{.*?\});", r.text)
            if not m:
                return None
            auth = json.loads(m.group(1))
            if email:
                refreshed = self._refresh_browser_auth(auth.get("token", ""), email)
                if refreshed:
                    return refreshed
            return auth
        except Exception:
            return None

    def _refresh_browser_auth(self, token: str, email: str) -> Optional[dict]:
        try:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["X-Inbox-Token"] = token
            r = self.session.post(
                f"{self.BASE_URL}/api/inbox-token",
                headers=headers,
                json={"email": email.strip().lower()},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and data.get("auth"):
                    return data["auth"]
        except Exception:
            pass
        return None

    def _api_headers(self, token: str) -> dict:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.BASE_URL}/",
            "User-Agent": self.USER_AGENT,
        }
        if token:
            headers["X-Inbox-Token"] = token
        return headers

    def _pack_token(self, token: str, email: str) -> str:
        return f"{token}|{quote(email)}"

    def _unpack_token(self, packed: str) -> Tuple[str, str]:
        if "|" in packed:
            token, email = packed.split("|", 1)
            return token, unquote(email)
        return packed, ""

    def create_email(self) -> Tuple[Optional[str], Optional[str]]:
        try:
            auth = self._load_browser_auth()
            token = (auth or {}).get("token", "")
            if not token:
                print(f"[{cfg.ts()}] [ERROR] [GPTMail] 初始化浏览器会话失败")
                return None, None

            r = self.session.get(
                f"{self.BASE_URL}/api/generate-email",
                headers=self._api_headers(token),
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                email = (data.get("data") or {}).get("email") or data.get("email")
                next_auth = data.get("auth") or auth
                next_token = next_auth.get("token", token)
                if email and next_token:
                    return email, self._pack_token(next_token, email)

            print(f"[{cfg.ts()}] [ERROR] [GPTMail] 创建邮箱失败，状态码: {r.status_code}, 内容: {r.text[:200]}")
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] [GPTMail] 创建异常: {e}")
        return None, None

    def get_inbox(self, token: str) -> List[dict]:
        try:
            inbox_token, email = self._unpack_token(token)
            if not email:
                return []

            r = self.session.get(
                f"{self.BASE_URL}/api/emails",
                headers=self._api_headers(inbox_token),
                params={"email": email},
                timeout=30,
            )
            if r.status_code in (401, 403):
                auth = self._load_browser_auth(email)
                inbox_token = (auth or {}).get("token", inbox_token)
                r = self.session.get(
                    f"{self.BASE_URL}/api/emails",
                    headers=self._api_headers(inbox_token),
                    params={"email": email},
                    timeout=30,
                )

            if r.status_code == 200:
                data = r.json()
                emails = ((data.get("data") or {}).get("emails") or []) if data.get("success") else []
                return [self._normalize_message(item) for item in emails]
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] [GPTMail] 获取邮件错误: {e}")
        return []

    def _normalize_message(self, item: dict) -> dict:
        content = item.get("content") or item.get("html_content") or ""
        preview = re.sub(r"<[^>]+>", " ", str(content))
        return {
            "_id": str(item.get("id", "")),
            "id": str(item.get("id", "")),
            "from": item.get("from_address", ""),
            "subject": item.get("subject", ""),
            "bodyPreview": preview,
            "body": content,
            "timestamp": item.get("timestamp") or item.get("created_at", ""),
        }
